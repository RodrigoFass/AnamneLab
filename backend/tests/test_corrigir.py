from datetime import date

import pytest

from app.conteudo import Conteudo
from app.pipeline.corrigir import (
    SISTEMA,
    TranscricaoNormalizada,
    calcular_notas,
    checklists_aplicaveis,
    corrigir,
    mensagem_feito,
)
from app.schemas.sessao import Avaliacao, ChecklistUsado
from app.texto import normalizar
from tests.apoio import LLMFixo, LLMRepete, falas_exemplo


def aprovar(conteudo: Conteudo, checklist_id: str) -> Conteudo:
    checklists = dict(conteudo.checklists)
    checklists[checklist_id] = checklists[checklist_id].model_copy(
        update={"status": "aprovado", "validado_por": "Prof. Teste", "validado_em": date(2026, 9, 1)}
    )
    return Conteudo(queixas=conteudo.queixas, checklists=checklists, cartoes=conteudo.cartoes, termo=conteudo.termo)


def resposta(*itens: tuple[str, bool, str | None]) -> dict:
    return {"itens": [{"item_id": i, "feito": f, "trecho": t} for i, f, t in itens]}


def por_id(resultado) -> dict:
    return {a.item_id: a for a in resultado.avaliacoes}


def test_trecho_inexistente_vira_faltou(conteudo):
    llm = LLMRepete(resposta(("idade", True, "Qual a sua data de nascimento?")))
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    idade = por_id(resultado)["idade"]
    assert idade.status == "faltou"
    assert idade.trecho is None
    assert idade.mensagem == "Faltou perguntar a idade."


def test_feito_sem_trecho_vira_faltou(conteudo):
    llm = LLMRepete(resposta(("idade", True, None), ("nome", True, "")))
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    assert por_id(resultado)["idade"].status == "faltou"
    assert por_id(resultado)["nome"].status == "faltou"


def test_item_ausente_na_resposta_vira_faltou_e_item_inventado_e_ignorado(conteudo):
    llm = LLMRepete(resposta(("item-que-nao-existe", True, "Quantos anos o senhor tem?")))
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    ids = [a.item_id for a in resultado.avaliacoes]
    assert "item-que-nao-existe" not in ids
    assert all(a.status == "faltou" for a in resultado.avaliacoes)


def test_trecho_confere_com_normalizacao(conteudo):
    llm = LLMRepete(
        resposta(
            ("idade", True, "  QUANTOS anos o senhor tem  "),  # caixa, espaços e sem '?'
            ("nome", True, "bom dia qual é o seu nome"),  # sem pontuação
            ("tabagismo", True, "Entrevistador: O senhor fuma?"),  # com o papel, como o LLM viu
        )
    )
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    avaliacoes = por_id(resultado)
    assert avaliacoes["idade"].status == "feito"
    assert avaliacoes["idade"].trecho == "QUANTOS anos o senhor tem"
    assert avaliacoes["nome"].status == "feito"
    assert avaliacoes["tabagismo"].status == "feito"


def test_normalizacao_mantem_acentos_e_palavras_inteiras():
    transcricao = TranscricaoNormalizada.de(falas_exemplo())
    assert normalizar("  Qual é o SEU nome?! ") == "qual é o seu nome"
    assert not transcricao.tem("qual e o seu nome")  # sem acento não é o mesmo texto
    assert not transcricao.tem("anos o sen")  # pedaço de palavra não vale
    assert not transcricao.tem("sim")  # curto demais para provar algo
    assert transcricao.tem("Quantos anos o senhor tem? Cinquenta e oito.")  # pergunta e resposta


def test_item_repetido_entre_checklists_conta_uma_vez(conteudo):
    llm = LLMRepete(resposta(("tabagismo", True, "O senhor fuma?")))
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    tabagismo = [a for a in resultado.avaliacoes if a.item_id == "tabagismo"]
    assert len(tabagismo) == 1
    assert tabagismo[0].checklist_id == "geral"
    # O LLM recebe o item uma vez só.
    ids_enviados = [i["id"] for i in llm.chamadas[0]["contexto"]["itens"]]
    assert ids_enviados.count("tabagismo") == 1
    assert len(resultado.avaliacoes) == 7


def test_notas_com_rascunho_contando_sao_provisorias(conteudo):
    llm = LLMRepete(
        resposta(
            ("nome", True, "Qual é o seu nome?"),  # geral, peso 2
            ("idade", True, "Quantos anos o senhor tem?"),  # geral, peso 3
            ("tabagismo", True, "O senhor fuma?"),  # geral, peso 3
            ("alergias", False, None),  # geral, peso 2
            ("irradiacao", True, "Essa dor vai para algum outro lugar?"),  # queixa, peso 3
            ("sudorese", False, None),  # queixa, peso 2
            ("sincope", False, None),  # queixa, peso 2
        )
    )
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    assert resultado.notas.geral == 80  # 8 de 10
    assert resultado.notas.queixa == 43  # 3 de 7 = 42,86
    assert resultado.notas.provisoria is True
    assert all(a.conta_na_nota for a in resultado.avaliacoes)


def test_arredondamento(conteudo):
    # geral: nome (2) + idade (3) feitos de 10 = 50; queixa: sudorese (2) de 7 = 28,57 -> 29
    llm = LLMRepete(
        resposta(
            ("nome", True, "Qual é o seu nome?"),
            ("idade", True, "Quantos anos o senhor tem?"),
            ("sudorese", True, "Suou frio junto com a dor?"),
        )
    )
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    assert resultado.notas.geral == 50
    assert resultado.notas.queixa == 29


def test_arredondamento_meio_sobe():
    def avaliacao(item_id: str, status: str, peso: int) -> Avaliacao:
        return Avaliacao(
            item_id=item_id,
            checklist_id="geral",
            secao="S",
            texto="T",
            status=status,
            trecho="x" if status == "feito" else None,
            mensagem="m",
            peso=peso,
            conta_na_nota=True,
        )

    avaliacoes = [avaliacao("a", "feito", 1), avaliacao("b", "faltou", 3), avaliacao("c", "faltou", 4)]
    usados = [ChecklistUsado(id="geral", versao=1, status="aprovado", conta_na_nota=True)]
    notas = calcular_notas(avaliacoes, usados, {"geral": "geral"})
    assert notas.geral == 13  # 1 de 8 = 12,5
    assert notas.queixa is None
    assert notas.provisoria is False


def test_rascunho_nao_conta_sem_contar_rascunho(conteudo):
    llm = LLMRepete(resposta(("idade", True, "Quantos anos o senhor tem?")))
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=False)
    assert resultado.notas.geral is None
    assert resultado.notas.queixa is None
    assert resultado.notas.provisoria is False
    assert not any(a.conta_na_nota for a in resultado.avaliacoes)
    # O item continua corrigido e aparece como sugestão, fora da nota.
    assert por_id(resultado)["idade"].status == "feito"
    assert all(not c.conta_na_nota for c in resultado.checklists_usados)


def test_so_aprovado_conta_sem_contar_rascunho(conteudo):
    conteudo = aprovar(conteudo, "geral")
    llm = LLMRepete(resposta(("idade", True, "Quantos anos o senhor tem?")))
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=False)
    assert resultado.notas.geral == 30  # 3 de 10
    assert resultado.notas.queixa is None  # dor torácica ainda é rascunho
    assert resultado.notas.provisoria is False


def test_aprovado_com_rascunho_contando(conteudo):
    conteudo = aprovar(conteudo, "geral")
    llm = LLMRepete(resposta(("idade", True, "Quantos anos o senhor tem?")))
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    assert resultado.notas.queixa == 0
    assert resultado.notas.provisoria is True  # a nota da queixa veio de rascunho


def test_registra_checklists_usados(conteudo):
    llm = LLMRepete(resposta())
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    usados = [(c.id, c.versao, c.status, c.conta_na_nota) for c in resultado.checklists_usados]
    assert usados == [("geral", 3, "rascunho", True), ("dor-toracica", 2, "rascunho", True)]


def test_outra_e_queixa_sem_checklist_usam_so_o_geral(conteudo):
    assert [c.id for c in checklists_aplicaveis(["outra"], conteudo)] == ["geral"]
    assert [c.id for c in checklists_aplicaveis(["cefaleia"], conteudo)] == ["geral"]
    llm = LLMRepete(resposta())
    resultado = corrigir(falas_exemplo(), ["outra"], conteudo, llm, contar_rascunho=True)
    assert {a.checklist_id for a in resultado.avaliacoes} == {"geral"}
    assert resultado.notas.queixa is None
    assert resultado.notas.geral == 0


def test_mensagens(conteudo):
    llm = LLMRepete(resposta(("idade", True, "Quantos anos o senhor tem?")))
    avaliacoes = por_id(corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True))
    assert avaliacoes["idade"].mensagem == "Você investigou: idade."
    assert avaliacoes["alergias"].mensagem == "Faltou perguntar sobre alergias."
    assert avaliacoes["alergias"].secao == "Hábitos e antecedentes"
    assert mensagem_feito("HAS e DM.") == "Você investigou: HAS e DM."


def test_correcao_pede_ao_llm_sem_palavras_chave_no_prompt(conteudo):
    llm = LLMRepete(resposta())
    corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    chamada = llm.chamadas[0]
    assert chamada["tarefa"] == "corrigir"
    assert "palavras_chave" not in chamada["mensagem"]
    assert "Entrevistador: Quantos anos o senhor tem?" in chamada["mensagem"]


@pytest.mark.parametrize("contar", [True, False])
def test_toda_avaliacao_feita_tem_trecho_que_existe(conteudo, contar):
    llm = LLMRepete(
        resposta(
            ("nome", True, "Qual é o seu nome?"),
            ("idade", True, "inventado pelo modelo"),
            ("sincope", True, None),
        )
    )
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=contar)
    transcricao = TranscricaoNormalizada.de(falas_exemplo())
    for avaliacao in resultado.avaliacoes:
        if avaliacao.status == "feito":
            assert transcricao.tem(avaliacao.trecho)
        else:
            assert avaliacao.trecho is None


def test_trecho_so_com_o_papel_nao_prova_nada(conteudo):
    llm = LLMRepete(
        resposta(
            ("idade", True, "Entrevistador"),
            ("nome", True, "Entrevistador:"),
            ("tabagismo", True, "Paciente: Entrevistador:"),
        )
    )
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    avaliacoes = por_id(resultado)
    assert avaliacoes["idade"].status == "faltou"
    assert avaliacoes["nome"].status == "faltou"
    assert avaliacoes["tabagismo"].status == "faltou"


# ---------- um pedido por checklist ----------


def _ids_pedidos(chamada) -> list[str]:
    return [i["id"] for i in chamada["contexto"]["itens"]]


def test_um_pedido_por_checklist_com_os_itens_de_cada_um(conteudo):
    llm = LLMRepete(resposta())
    corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    assert len(llm.chamadas) == 2
    geral, queixa = llm.chamadas
    assert _ids_pedidos(geral) == ["nome", "idade", "tabagismo", "alergias"]
    # 'tabagismo' também está no checklist da queixa, mas conta uma vez só, no geral.
    assert _ids_pedidos(queixa) == ["irradiacao", "sudorese", "sincope"]
    assert "Checklist geral" in geral["mensagem"]
    assert "específico da queixa" in queixa["mensagem"]
    assert "Entrevistador: Quantos anos o senhor tem?" in queixa["mensagem"]


def test_outra_faz_um_pedido_so(conteudo):
    llm = LLMRepete(resposta())
    corrigir(falas_exemplo(), ["outra"], conteudo, llm, contar_rascunho=True)
    assert len(llm.chamadas) == 1


def test_a_mesma_fala_vale_no_geral_e_na_queixa(conteudo):
    """O que dava nota 0 na queixa: um trecho que já provou um item do geral vale também no da queixa."""
    fala = "Essa dor vai para algum outro lugar?"
    llm = LLMFixo(resposta(("idade", True, fala)), resposta(("irradiacao", True, fala)))
    avaliacoes = por_id(corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True))
    assert avaliacoes["idade"].status == "feito"
    assert avaliacoes["irradiacao"].status == "feito"
    assert avaliacoes["irradiacao"].trecho == fala


def test_registro_de_item_que_nao_foi_pedido_e_ignorado(conteudo):
    # O pedido do geral responde por um item da queixa; só vale o que o pedido da queixa disse.
    llm = LLMFixo(
        resposta(("irradiacao", True, "Essa dor vai para algum outro lugar?")),
        resposta(("irradiacao", False, None)),
    )
    avaliacoes = por_id(corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True))
    assert avaliacoes["irradiacao"].status == "faltou"


def test_instrucoes_deixam_a_mesma_fala_provar_varios_itens():
    assert "A mesma fala pode provar vários itens" in SISTEMA
    assert "outras palavras" in SISTEMA
