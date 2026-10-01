import pytest

from app.llm.falso import ClienteFalso
from app.pipeline.corrigir import ErroContestacao, contestar, corrigir, item_do_checklist
from app.schemas.sessao import ContestacaoCriar
from tests.apoio import LLMFixo, falas_exemplo

CONFIRMA = {"cumpre": True}
NEGA = {"cumpre": False}


@pytest.fixture
def correcao(conteudo):
    llm = LLMFixo(
        {
            "itens": [
                {"item_id": "nome", "feito": True, "trecho": "Qual é o seu nome?"},
                {"item_id": "idade", "feito": False, "trecho": None},
                {"item_id": "tabagismo", "feito": True, "trecho": "O senhor fuma?"},
                {"item_id": "irradiacao", "feito": False, "trecho": None},
            ]
        }
    )
    return corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)


def _contestar(correcao, conteudo, llm=None, **pedido):
    avaliacao = next((a for a in correcao.avaliacoes if a.item_id == pedido["item_id"]), None)
    item = item_do_checklist(conteudo, avaliacao.checklist_id, pedido["item_id"]) if avaliacao else None
    return contestar(
        correcao.avaliacoes,
        falas_exemplo(),
        ContestacaoCriar(motivo="Eu perguntei isso.", **pedido),
        correcao.checklists_usados,
        conteudo.tipos_checklists(),
        correcao.notas,
        item=item,
        llm=llm if llm is not None else LLMFixo(CONFIRMA),
    )


def _pendente_sem_mudar_a_nota(resultado, correcao, item_id="idade"):
    avaliacao = next(a for a in resultado.avaliacoes if a.item_id == item_id)
    assert resultado.contestacao.resultado == "pendente_professor"
    assert avaliacao.status == "faltou"
    assert avaliacao.trecho is None
    assert avaliacao.contestacao is not None and avaliacao.contestacao.resultado == "pendente_professor"
    assert resultado.notas == correcao.notas


def test_trecho_que_existe_e_o_llm_confirma_torna_o_item_feito(correcao, conteudo):
    assert correcao.notas.geral == 50  # nome (2) + tabagismo (3) de 10
    llm = LLMFixo(CONFIRMA)
    resultado = _contestar(correcao, conteudo, llm=llm, item_id="idade", trecho="quantos anos o senhor tem")
    idade = next(a for a in resultado.avaliacoes if a.item_id == "idade")
    assert resultado.contestacao.resultado == "procedente"
    assert idade.status == "feito"
    assert idade.trecho == "quantos anos o senhor tem"
    assert idade.mensagem == "Você investigou: idade."
    assert idade.contestacao is not None and idade.contestacao.resultado == "procedente"
    assert resultado.notas.geral == 80
    assert resultado.notas.queixa == correcao.notas.queixa
    assert resultado.notas.provisoria is True
    # O LLM recebeu o item, a pergunta de exemplo e o trecho.
    chamada = llm.chamadas[0]
    assert chamada["tarefa"] == "verificar_contestacao"
    assert "Idade" in chamada["mensagem"]
    assert "quantos anos o senhor tem" in chamada["mensagem"]
    assert chamada["contexto"]["item"]["palavras_chave"] == ["quantos anos"]


def test_trecho_que_existe_mas_o_llm_nega_fica_pendente(correcao, conteudo):
    resultado = _contestar(correcao, conteudo, llm=LLMFixo(NEGA), item_id="idade", trecho="O senhor fuma?")
    _pendente_sem_mudar_a_nota(resultado, correcao)


def test_falha_do_llm_fica_pendente_sem_bloquear_o_aluno(correcao, conteudo):
    llm = LLMFixo("{isso não é json", '{"cumpre": "talvez"}')
    resultado = _contestar(correcao, conteudo, llm=llm, item_id="idade", trecho="Quantos anos o senhor tem?")
    _pendente_sem_mudar_a_nota(resultado, correcao)
    assert len(llm.chamadas) == 2  # uma nova tentativa, depois desiste


def test_trecho_que_nao_existe_fica_pendente_sem_chamar_o_llm(correcao, conteudo):
    llm = LLMFixo(CONFIRMA)
    resultado = _contestar(correcao, conteudo, llm=llm, item_id="idade", trecho="Qual é a sua idade?")
    _pendente_sem_mudar_a_nota(resultado, correcao)
    assert llm.chamadas == []


def test_llm_falso_confere_as_palavras_chave_do_item(correcao, conteudo):
    llm = ClienteFalso()
    sem_relacao = _contestar(correcao, conteudo, llm=llm, item_id="idade", trecho="O senhor fuma?")
    _pendente_sem_mudar_a_nota(sem_relacao, correcao)
    com_relacao = _contestar(correcao, conteudo, llm=llm, item_id="idade", trecho="Quantos anos o senhor tem?")
    assert com_relacao.contestacao.resultado == "procedente"


def test_contestacao_na_queixa_recalcula_a_nota_da_queixa(correcao, conteudo):
    resultado = _contestar(correcao, conteudo, item_id="irradiacao", trecho="Essa dor vai para algum outro lugar?")
    assert resultado.notas.queixa > correcao.notas.queixa
    assert resultado.notas.geral == correcao.notas.geral


@pytest.mark.parametrize(
    "trecho",
    [None, "", "Perguntei se ele tinha alergia a remédio.", "sim", "Entrevistador:", "Paciente: Entrevistador:"],
)
def test_sem_trecho_valido_fica_pendente_e_a_nota_nao_muda(correcao, conteudo, trecho):
    llm = LLMFixo(CONFIRMA)
    resultado = _contestar(correcao, conteudo, llm=llm, item_id="idade", trecho=trecho)
    _pendente_sem_mudar_a_nota(resultado, correcao)
    assert llm.chamadas == []


def test_nao_contesta_item_feito(correcao, conteudo):
    with pytest.raises(ErroContestacao) as erro:
        _contestar(correcao, conteudo, item_id="nome", trecho="Qual é o seu nome?")
    assert erro.value.codigo == 409


def test_nao_contesta_item_que_nao_esta_na_correcao(correcao, conteudo):
    with pytest.raises(ErroContestacao) as erro:
        _contestar(correcao, conteudo, item_id="inexistente", trecho="Qual é o seu nome?")
    assert erro.value.codigo == 404


def test_contestacao_nao_altera_as_outras_avaliacoes(correcao, conteudo):
    resultado = _contestar(correcao, conteudo, item_id="idade", trecho="Quantos anos o senhor tem?")
    antes = {a.item_id: a for a in correcao.avaliacoes if a.item_id != "idade"}
    depois = {a.item_id: a for a in resultado.avaliacoes if a.item_id != "idade"}
    assert antes == depois
