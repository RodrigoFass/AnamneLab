"""Perguntas sugeridas: terceira camada da correção, só quando falta critério."""

import pytest

from app.llm.falso import ClienteFalso
from app.pipeline.corrigir import corrigir
from app.pipeline.sugestoes import gerar_sugestoes, queixas_sem_checklist
from tests.apoio import LLMFixo, falas_exemplo

RESPOSTA = {
    "hipoteses": [{"nome": "Síndrome coronariana aguda", "a_favor": ["Dor ao esforço."], "contra": []}],
    "perguntas_sugeridas": ["A dor piora quando respira fundo?", "  "],
    "sobre_hipoteses_aluno": [
        {"nome": "angina estável", "a_favor": ["Dor ao subir escada."], "contra": [" ", "Falta saber a duração."]},
        {"nome": "Hipótese que o aluno não escreveu", "a_favor": [], "contra": []},
    ],
}


def _gerar(conteudo, queixas, llm, descricao_outra=None):
    falas = falas_exemplo()
    correcao = corrigir(falas, queixas, conteudo, ClienteFalso(), contar_rascunho=True)
    return gerar_sugestoes(falas, queixas, descricao_outra, ["Angina"], correcao.avaliacoes, conteudo, llm)


def test_queixa_com_checklist_sai_sem_perguntas_mesmo_que_o_llm_mande(conteudo):
    llm = LLMFixo(RESPOSTA)
    sugestoes = _gerar(conteudo, ["dor-toracica"], llm)
    assert sugestoes.perguntas_sugeridas == []
    assert [h.nome for h in sugestoes.hipoteses] == ["Síndrome coronariana aguda"]
    chamada = llm.chamadas[0]
    assert chamada["contexto"]["pedir_perguntas"] is False
    assert "sem checklist" not in chamada["mensagem"]


@pytest.mark.parametrize(
    ("queixas", "descricao", "nome"),
    [
        (["cefaleia"], None, "Cefaleia"),
        (["outra"], "Dor no calcanhar", "Dor no calcanhar"),
        (["dor-toracica", "cefaleia"], None, "Cefaleia"),
    ],
)
def test_queixa_sem_criterio_recebe_perguntas(conteudo, queixas, descricao, nome):
    llm = LLMFixo(RESPOSTA)
    sugestoes = _gerar(conteudo, queixas, llm, descricao_outra=descricao)
    assert sugestoes.perguntas_sugeridas == ["A dor piora quando respira fundo?"]
    chamada = llm.chamadas[0]
    assert chamada["contexto"]["pedir_perguntas"] is True
    assert f"Queixa sem checklist no app: {nome}." in chamada["mensagem"]


def test_queixas_sem_checklist(conteudo):
    assert queixas_sem_checklist(["dor-toracica"], conteudo) == []
    assert queixas_sem_checklist(["dor-toracica", "cefaleia"], conteudo) == ["cefaleia"]
    assert queixas_sem_checklist(["outra"], conteudo) == ["outra"]


def test_falso_segue_a_mesma_regra(conteudo):
    assert _gerar(conteudo, ["dor-toracica"], ClienteFalso()).perguntas_sugeridas == []
    assert _gerar(conteudo, ["cefaleia"], ClienteFalso()).perguntas_sugeridas


def test_comenta_as_hipoteses_do_aluno_com_o_nome_que_ele_escreveu(conteudo):
    llm = LLMFixo(RESPOSTA)
    sugestoes = _gerar(conteudo, ["dor-toracica"], llm)
    assert len(sugestoes.sobre_hipoteses_aluno) == 1  # uma por hipótese do aluno, no máximo
    sobre = sugestoes.sobre_hipoteses_aluno[0]
    assert sobre.nome == "Angina"
    assert sobre.contra == ["Falta saber a duração."]


def test_manda_os_itens_ja_investigados_para_nao_cobrar_de_novo(conteudo):
    llm = LLMFixo(RESPOSTA)
    _gerar(conteudo, ["dor-toracica"], llm)
    assert "já investigados (não diga que faltam)" in llm.chamadas[0]["mensagem"]
