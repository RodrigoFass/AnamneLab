from app.llm.falso import ClienteFalso
from app.pipeline.queixa import detectar_queixa
from app.pipeline.rotular_falas import rotular_falas
from app.pipeline.transcrever import TranscritorFalso
from tests.apoio import LLMFixo, falas_exemplo


def _detectar(conteudo, resposta):
    return detectar_queixa(falas_exemplo(), conteudo.queixas, LLMFixo(resposta))


def test_id_fora_da_lista_vira_outra(conteudo):
    detectada = _detectar(
        conteudo, {"queixas": ["dor-no-dedao"], "descricao_outra": "Dor no dedão", "trecho": "Dói o dedão."}
    )
    assert detectada.queixas == ["outra"]
    assert detectada.descricao_outra == "Dor no dedão"


def test_mistura_mantem_os_validos_e_tira_repetidos(conteudo):
    detectada = _detectar(
        conteudo,
        {"queixas": ["dor-toracica", "inventada", "dor-toracica", "outra"], "descricao_outra": "x", "trecho": "t"},
    )
    # 'outra' vale sozinha: com uma queixa da lista, fica só a da lista.
    assert detectada.queixas == ["dor-toracica"]
    assert detectada.descricao_outra is None


def test_lista_vazia_vira_outra(conteudo):
    detectada = _detectar(conteudo, {"queixas": [], "descricao_outra": None, "trecho": ""})
    assert detectada.queixas == ["outra"]
    assert detectada.descricao_outra is None


def test_queixa_da_lista_nao_leva_descricao_outra(conteudo):
    detectada = _detectar(
        conteudo, {"queixas": ["cefaleia"], "descricao_outra": "algo inventado", "trecho": "Dor de cabeça."}
    )
    assert detectada.queixas == ["cefaleia"]
    assert detectada.descricao_outra is None


def test_prompt_leva_a_lista_fechada(conteudo):
    llm = LLMFixo({"queixas": ["dor-toracica"], "descricao_outra": None, "trecho": "t"})
    detectar_queixa(falas_exemplo(), conteudo.queixas, llm)
    assert '"dor-toracica"' in llm.chamadas[0]["mensagem"]
    assert '"cefaleia"' in llm.chamadas[0]["mensagem"]


def test_falso_reconhece_pelos_sinonimos(conteudo):
    llm = ClienteFalso()
    falas = rotular_falas(TranscritorFalso().transcrever(None), llm)
    detectada = detectar_queixa(falas, conteudo.queixas, llm)
    assert detectada.queixas[0] == "dor-toracica"
    assert "dor no peito" in detectada.trecho
