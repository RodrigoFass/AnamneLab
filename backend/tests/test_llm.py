import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.config import Settings
from app.llm import ErroLLM, obter_cliente_llm, schema_para_llm
from app.llm.anthropic import (
    BETA_FALLBACK,
    MENSAGEM_LONGA,
    MENSAGEM_OCUPADO,
    MENSAGEM_RECUSA,
    MENSAGEM_SEM_CONEXAO,
    ClienteAnthropic,
)
from app.llm.base import LEMBRETE_NOVA_TENTATIVA, MENSAGEM_PADRAO
from app.llm.falso import ClienteFalso
from app.schemas import llm as modelos_llm
from app.schemas.llm import (
    AnamneseEstruturada,
    CorrecaoLLM,
    FalasRotuladas,
    QueixaDetectada,
    SugestoesIA,
)
from tests.apoio import LLMFixo

VALIDO = {"queixas": ["dor-toracica"], "descricao_outra": None, "trecho": "Dor no peito."}


def _gerar(cliente):
    return cliente.gerar(tarefa="queixa", sistema="s", mensagem="m", saida=QueixaDetectada)


# ---------- regra 7: validação e uma nova tentativa ----------


def test_json_valido_na_primeira():
    llm = LLMFixo(VALIDO)
    assert _gerar(llm).queixas == ["dor-toracica"]
    assert len(llm.chamadas) == 1


def test_json_invalido_ganha_uma_nova_tentativa():
    llm = LLMFixo("{isso não é json", VALIDO)
    assert _gerar(llm).trecho == "Dor no peito."
    assert len(llm.chamadas) == 2
    assert llm.chamadas[1]["mensagem"].endswith(LEMBRETE_NOVA_TENTATIVA)


def test_json_invalido_duas_vezes_vira_erro_claro():
    llm = LLMFixo("{isso não é json", '{"queixas": "fora do formato"}', VALIDO)
    with pytest.raises(ErroLLM) as erro:
        _gerar(llm)
    assert erro.value.mensagem == MENSAGEM_PADRAO
    assert len(llm.chamadas) == 2  # só uma nova tentativa


def test_campo_a_mais_conta_como_invalido():
    llm = LLMFixo({**VALIDO, "diagnostico": "infarto"}, {**VALIDO, "diagnostico": "infarto"})
    with pytest.raises(ErroLLM):
        _gerar(llm)


# ---------- schema da saída estruturada ----------


def _objetos(no):
    if isinstance(no, dict):
        if no.get("type") == "object":
            yield no
        for valor in no.values():
            yield from _objetos(valor)
    elif isinstance(no, list):
        for valor in no:
            yield from _objetos(valor)


@pytest.mark.parametrize("modelo", [FalasRotuladas, QueixaDetectada, AnamneseEstruturada, CorrecaoLLM, SugestoesIA])
def test_schema_fecha_todos_os_objetos(modelo):
    schema = schema_para_llm(modelo)
    objetos = list(_objetos(schema))
    assert objetos
    assert all(o.get("additionalProperties") is False for o in objetos)
    if "$defs" in modelo.model_json_schema():
        assert set(schema["$defs"]) == set(modelo.model_json_schema()["$defs"])


def test_todos_os_modelos_do_llm_proibem_campos_extras():
    for nome in dir(modelos_llm):
        modelo = getattr(modelos_llm, nome)
        if (
            isinstance(modelo, type)
            and issubclass(modelo, modelos_llm.BaseModel)
            and modelo is not modelos_llm.BaseModel
        ):
            assert modelo.model_config.get("extra") == "forbid", nome


# ---------- provedor Anthropic com um client falso ----------


class FakeMessages:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def create(self, **kwargs):
        self.chamadas.append(kwargs)
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


class FakeAnthropic:
    def __init__(self, *respostas):
        self.beta = SimpleNamespace(messages=FakeMessages(respostas))


def mensagem(stop_reason="end_turn", texto=None, categoria=None):
    conteudo = [SimpleNamespace(type="thinking", thinking="")]
    if texto is not None:
        conteudo.append(SimpleNamespace(type="text", text=texto))
    detalhes = SimpleNamespace(type="refusal", category=categoria, explanation=None) if categoria else None
    return SimpleNamespace(stop_reason=stop_reason, stop_details=detalhes, content=conteudo)


def _cliente(*respostas, **config):
    settings = Settings(_env_file=None, llm_provedor="anthropic", **config)
    fake = FakeAnthropic(*respostas)
    return ClienteAnthropic(settings, client=fake), fake.beta.messages


def test_anthropic_monta_o_pedido_sem_temperatura():
    cliente, fake = _cliente(mensagem(texto=json.dumps(VALIDO)))
    assert _gerar(cliente).queixas == ["dor-toracica"]
    pedido = fake.chamadas[0]
    assert pedido["model"] == "claude-opus-5-5"
    assert pedido["max_tokens"] == 16000
    assert pedido["system"] == "s"
    assert pedido["messages"] == [{"role": "user", "content": "m"}]
    assert pedido["output_config"]["effort"] == "medium"
    assert pedido["output_config"]["format"]["type"] == "json_schema"
    assert pedido["output_config"]["format"]["schema"] == schema_para_llm(QueixaDetectada)
    assert pedido["betas"] == [BETA_FALLBACK]
    assert pedido["fallbacks"] == "default"
    for proibido in ("temperature", "top_p", "top_k", "thinking"):
        assert proibido not in pedido


def test_anthropic_usa_modelo_e_esforco_da_configuracao():
    cliente, fake = _cliente(mensagem(texto=json.dumps(VALIDO)), llm_modelo="claude-sonnet-5-5", llm_esforco="high")
    _gerar(cliente)
    assert fake.chamadas[0]["model"] == "claude-sonnet-5-5"
    assert fake.chamadas[0]["output_config"]["effort"] == "high"


def test_anthropic_recusa_vira_erro_sem_nova_tentativa():
    cliente, fake = _cliente(mensagem("refusal", categoria="bio"), mensagem(texto=json.dumps(VALIDO)))
    with pytest.raises(ErroLLM) as erro:
        _gerar(cliente)
    assert erro.value.mensagem == MENSAGEM_RECUSA
    assert len(fake.chamadas) == 1


def test_anthropic_limite_de_tokens_vira_erro():
    cliente, _ = _cliente(mensagem("max_tokens", texto='{"queixas": ['))
    with pytest.raises(ErroLLM) as erro:
        _gerar(cliente)
    assert erro.value.mensagem == MENSAGEM_LONGA


def test_anthropic_json_invalido_duas_vezes():
    cliente, fake = _cliente(mensagem(texto="não é json"), mensagem(texto="{}"))
    with pytest.raises(ErroLLM) as erro:
        _gerar(cliente)
    assert erro.value.mensagem == MENSAGEM_PADRAO
    assert len(fake.chamadas) == 2


def test_anthropic_sem_bloco_de_texto():
    cliente, _ = _cliente(mensagem(texto=None))
    with pytest.raises(ErroLLM):
        _gerar(cliente)


_PEDIDO = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.mark.parametrize(
    ("erro", "esperada"),
    [
        (
            anthropic.RateLimitError("limite", response=httpx2.Response(429, request=_PEDIDO), body=None),
            MENSAGEM_OCUPADO,
        ),
        (
            anthropic.InternalServerError("falha", response=httpx2.Response(500, request=_PEDIDO), body=None),
            MENSAGEM_PADRAO,
        ),
        (anthropic.BadRequestError("ruim", response=httpx2.Response(400, request=_PEDIDO), body=None), MENSAGEM_PADRAO),
        (anthropic.APIConnectionError(request=_PEDIDO), MENSAGEM_SEM_CONEXAO),
        (anthropic.APITimeoutError(request=_PEDIDO), MENSAGEM_SEM_CONEXAO),
    ],
)
def test_anthropic_erros_do_sdk_viram_erro_llm(erro, esperada):
    cliente, _ = _cliente(erro)
    with pytest.raises(ErroLLM) as capturado:
        _gerar(cliente)
    assert capturado.value.mensagem == esperada


# ---------- fábrica e provedor falso ----------


def test_fabrica_usa_o_falso_por_padrao():
    assert isinstance(obter_cliente_llm(Settings(_env_file=None, llm_provedor="falso")), ClienteFalso)


def test_falso_rotula_pelos_marcadores():
    falas = (
        ClienteFalso()
        .gerar(
            tarefa="rotular",
            sistema="",
            mensagem="",
            saida=FalasRotuladas,
            contexto={"texto": "Médico: Qual o seu nome?\nPaciente: Ana.\nMédico: Quantos anos?\nPaciente: Trinta."},
        )
        .falas
    )
    assert [(f.papel, f.texto) for f in falas] == [
        ("entrevistador", "Qual o seu nome?"),
        ("paciente", "Ana."),
        ("entrevistador", "Quantos anos?"),
        ("paciente", "Trinta."),
    ]


def test_falso_rotula_alternando_sem_marcadores():
    falas = (
        ClienteFalso()
        .gerar(
            tarefa="rotular",
            sistema="",
            mensagem="",
            saida=FalasRotuladas,
            contexto={"texto": "Qual o seu nome? Ana. Quantos anos? Trinta."},
        )
        .falas
    )
    assert [f.papel for f in falas] == ["entrevistador", "paciente", "entrevistador", "paciente"]


def test_falso_anamnese_marca_o_que_nao_foi_abordado():
    anamnese = ClienteFalso().gerar(
        tarefa="anamnese",
        sistema="",
        mensagem="",
        saida=AnamneseEstruturada,
        contexto={
            "falas": [
                {"papel": "entrevistador", "texto": "O que trouxe a senhora aqui?"},
                {"papel": "paciente", "texto": "Dor de cabeça há três dias."},
            ]
        },
    )
    assert anamnese.queixa_principal == "Dor de cabeça há três dias."
    assert anamnese.antecedentes_familiares == "Não abordado."


def test_falso_sugestoes_sao_exemplo_e_perguntas_vem_dos_itens_faltantes():
    sugestoes = ClienteFalso().gerar(
        tarefa="sugestoes",
        sistema="",
        mensagem="",
        saida=SugestoesIA,
        contexto={"itens_faltantes": [{"id": "alergias", "texto": "Alergias"}]},
    )
    assert "exemplo" in sugestoes.hipoteses[0].nome.lower()
    assert sugestoes.perguntas_sugeridas == ["Alergias"]


def test_anthropic_com_o_sdk_de_verdade_sem_rede():
    """O SDK real monta o pedido HTTP; um transporte falso responde. Nada sai da máquina."""
    pedidos: list[httpx2.Request] = []

    def responder(pedido: httpx2.Request) -> httpx2.Response:
        pedidos.append(pedido)
        return httpx2.Response(
            200,
            json={
                "id": "msg_teste",
                "type": "message",
                "role": "assistant",
                "model": "claude-opus-5-5",
                "content": [{"type": "text", "text": json.dumps(VALIDO)}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 10},
            },
        )

    sdk = anthropic.Anthropic(
        api_key="chave-de-teste", http_client=httpx2.Client(transport=httpx2.MockTransport(responder)), max_retries=0
    )
    cliente = ClienteAnthropic(Settings(_env_file=None, llm_provedor="anthropic"), client=sdk)
    assert _gerar(cliente).queixas == ["dor-toracica"]

    corpo = json.loads(pedidos[0].content)
    assert pedidos[0].url.path == "/v1/messages"
    assert BETA_FALLBACK in pedidos[0].headers["anthropic-beta"]
    assert corpo["fallbacks"] == "default"
    assert corpo["output_config"]["format"]["type"] == "json_schema"
    assert corpo["output_config"]["effort"] == "medium"
    assert "temperature" not in corpo and "thinking" not in corpo
