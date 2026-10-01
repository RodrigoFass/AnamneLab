from app.llm.falso import ClienteFalso
from app.pipeline.queixa import detectar_queixa
from app.pipeline.rotular_falas import rotular_falas
from app.pipeline.transcrever import TranscritorFalso
from app.schemas.llm import Fala
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
    assert detectada.queixas == ["dor-toracica"]
    assert "dor no peito" in detectada.trecho


def _falas(*pares: tuple[str, str]) -> list[Fala]:
    return [Fala(papel=papel, texto=texto) for papel, texto in pares]


def test_falso_ignora_sintoma_que_surge_depois_das_primeiras_falas(conteudo):
    falas = _falas(
        ("entrevistador", "Qual é o seu nome?"),
        ("paciente", "Maria."),
        ("entrevistador", "O que trouxe a senhora aqui?"),
        ("paciente", "Uma dor no calcanhar que não passa."),
        ("entrevistador", "Desde quando?"),
        ("paciente", "Faz uma semana."),
        ("entrevistador", "Piora quando pisa?"),
        ("paciente", "Piora de manhã."),
        ("entrevistador", "Mais alguma coisa?"),
        ("paciente", "Às vezes tenho dor de cabeça."),
    )
    detectada = detectar_queixa(falas, conteudo.queixas, ClienteFalso())
    assert detectada.queixas == ["outra"]
    assert detectada.trecho == "Uma dor no calcanhar que não passa."


def test_falso_devolve_so_a_primeira_queixa_que_casar(conteudo):
    falas = _falas(
        ("entrevistador", "O que traz o senhor hoje?"),
        ("paciente", "Dor de cabeça desde ontem."),
        ("entrevistador", "Algo mais?"),
        ("paciente", "E um aperto no peito."),
    )
    detectada = detectar_queixa(falas, conteudo.queixas, ClienteFalso())
    assert detectada.queixas == ["cefaleia"]
