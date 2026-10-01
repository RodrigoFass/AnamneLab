import pytest

from app.pipeline.corrigir import ErroContestacao, contestar, corrigir
from app.schemas.sessao import ContestacaoCriar
from tests.apoio import LLMFixo, falas_exemplo


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


def _contestar(correcao, conteudo, **pedido):
    return contestar(
        correcao.avaliacoes,
        falas_exemplo(),
        ContestacaoCriar(motivo="Eu perguntei isso.", **pedido),
        correcao.checklists_usados,
        conteudo.tipos_checklists(),
        correcao.notas,
    )


def test_trecho_que_existe_torna_o_item_feito_e_recalcula_a_nota(correcao, conteudo):
    assert correcao.notas.geral == 50  # nome (2) + tabagismo (3) de 10
    resultado = _contestar(correcao, conteudo, item_id="idade", trecho="quantos anos o senhor tem")
    idade = next(a for a in resultado.avaliacoes if a.item_id == "idade")
    assert resultado.contestacao.resultado == "procedente"
    assert idade.status == "feito"
    assert idade.trecho == "quantos anos o senhor tem"
    assert idade.mensagem == "Você investigou: idade."
    assert idade.contestacao is not None and idade.contestacao.resultado == "procedente"
    assert resultado.notas.geral == 80
    assert resultado.notas.queixa == correcao.notas.queixa
    assert resultado.notas.provisoria is True


def test_contestacao_na_queixa_recalcula_a_nota_da_queixa(correcao, conteudo):
    resultado = _contestar(correcao, conteudo, item_id="irradiacao", trecho="Essa dor vai para algum outro lugar?")
    assert resultado.notas.queixa > correcao.notas.queixa
    assert resultado.notas.geral == correcao.notas.geral


@pytest.mark.parametrize(
    "trecho",
    [None, "", "Perguntei se ele tinha alergia a remédio.", "sim", "Entrevistador:", "Paciente: Entrevistador:"],
)
def test_sem_trecho_valido_fica_pendente_e_a_nota_nao_muda(correcao, conteudo, trecho):
    resultado = _contestar(correcao, conteudo, item_id="idade", trecho=trecho)
    idade = next(a for a in resultado.avaliacoes if a.item_id == "idade")
    assert resultado.contestacao.resultado == "pendente_professor"
    assert idade.status == "faltou"
    assert idade.trecho is None
    assert idade.contestacao is not None and idade.contestacao.resultado == "pendente_professor"
    assert resultado.notas == correcao.notas


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
