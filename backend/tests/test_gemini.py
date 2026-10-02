import json
import logging

import httpx
import pytest

from app.config import Settings
from app.llm import ErroLLM, obter_cliente_llm
from app.llm.base import LEMBRETE_NOVA_TENTATIVA, MENSAGEM_PADRAO
from app.llm.gemini import (
    MENSAGEM_CONTA,
    MENSAGEM_COTA,
    MENSAGEM_COTA_DIA,
    MENSAGEM_LONGA,
    MENSAGEM_RECUSA,
    MENSAGEM_SEM_CHAVE,
    MENSAGEM_SEM_CONEXAO,
    ClienteGemini,
    schema_para_gemini,
)
from app.schemas.llm import AnamneseEstruturada, CorrecaoLLM, FalasRotuladas, QueixaDetectada, SugestoesIA

VALIDO = {"queixas": ["dor-toracica"], "descricao_outra": None, "trecho": "Dor no peito."}
SEGREDO = "Carlos Alberto, 54 anos, mora na rua tal"
"""Texto que faz as vezes de transcrição: não pode aparecer em log nenhum."""


def _settings(**extra) -> Settings:
    valores = {"llm_provedor": "gemini", "gemini_api_key": "chave-de-teste", "gemini_modelos": "modelo-a, modelo-b"}
    return Settings(_env_file=None, **{**valores, **extra})


def _resposta_ok(texto, *, parada="STOP", partes=None) -> httpx.Response:
    if not isinstance(texto, str):
        texto = json.dumps(texto, ensure_ascii=False)
    corpo = {
        "candidates": [{"content": {"role": "model", "parts": partes or [{"text": texto}]}, "finishReason": parada}]
    }
    return httpx.Response(200, json=corpo)


def _erro(status_http: int, status: str, mensagem: str = "erro do Google", motivo: str | None = None) -> httpx.Response:
    erro = {"code": status_http, "message": mensagem, "status": status}
    if motivo:
        erro["details"] = [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": motivo}]
    return httpx.Response(status_http, json={"error": erro})


class Servidor:
    """Responde, na ordem, com as respostas dadas e guarda os pedidos."""

    def __init__(self, *respostas: httpx.Response | Exception) -> None:
        self.respostas = list(respostas)
        self.pedidos: list[httpx.Request] = []

    def __call__(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    def modelos(self) -> list[str]:
        return [p.url.path.rsplit("/", 1)[-1].removesuffix(":generateContent") for p in self.pedidos]


def _cliente(servidor: Servidor, **extra) -> ClienteGemini:
    http = httpx.Client(base_url="https://gemini.teste/v1beta", transport=httpx.MockTransport(servidor))
    cliente = ClienteGemini(_settings(**extra), client=http)
    cliente.espera_nova_tentativa_s = 0
    return cliente


def _gerar(cliente: ClienteGemini, mensagem: str = "m"):
    return cliente.gerar(tarefa="queixa", sistema="sistema", mensagem=mensagem, saida=QueixaDetectada)


# ---------- pedido ----------


def test_fabrica_devolve_o_gemini():
    assert isinstance(obter_cliente_llm(_settings()), ClienteGemini)


def test_lista_de_modelos_ignora_espacos_e_vazios():
    assert _settings(gemini_modelos=" a ,, b ,").lista_modelos_gemini == ["a", "b"]


def test_monta_o_pedido_com_schema_e_sem_temperatura():
    servidor = Servidor(_resposta_ok(VALIDO))
    assert _gerar(_cliente(servidor)).queixas == ["dor-toracica"]

    pedido = servidor.pedidos[0]
    assert pedido.method == "POST"
    assert pedido.url.path == "/v1beta/models/modelo-a:generateContent"
    assert pedido.headers["x-goog-api-key"] == "chave-de-teste"
    assert "key=" not in str(pedido.url)  # a chave vai no cabeçalho, nunca na URL
    corpo = json.loads(pedido.content)
    assert corpo["systemInstruction"] == {"parts": [{"text": "sistema"}]}
    assert corpo["contents"] == [{"role": "user", "parts": [{"text": "m"}]}]
    config = corpo["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert config["responseJsonSchema"] == schema_para_gemini(QueixaDetectada)
    assert "temperature" not in json.dumps(corpo)


def _refs(no):
    if isinstance(no, dict):
        if "$ref" in no:
            yield no["$ref"]
        for valor in no.values():
            yield from _refs(valor)
    elif isinstance(no, list):
        for valor in no:
            yield from _refs(valor)


@pytest.mark.parametrize("modelo", [FalasRotuladas, QueixaDetectada, AnamneseEstruturada, CorrecaoLLM, SugestoesIA])
def test_schema_do_gemini_nao_tem_referencias_e_fecha_os_objetos(modelo):
    schema = schema_para_gemini(modelo)
    assert "$defs" not in schema
    assert list(_refs(schema)) == []
    texto = json.dumps(schema)
    assert '"additionalProperties": true' not in texto
    assert schema["additionalProperties"] is False


def test_ignora_partes_de_raciocinio():
    partes = [{"text": "pensando...", "thought": True}, {"text": json.dumps(VALIDO)}]
    servidor = Servidor(_resposta_ok("", partes=partes))
    assert _gerar(_cliente(servidor)).trecho == "Dor no peito."


# ---------- regra 7 ----------


def test_json_invalido_ganha_uma_nova_tentativa():
    servidor = Servidor(_resposta_ok("{isso não é json"), _resposta_ok(VALIDO))
    assert _gerar(_cliente(servidor)).queixas == ["dor-toracica"]
    segunda = json.loads(servidor.pedidos[1].content)
    assert segunda["contents"][0]["parts"][0]["text"].endswith(LEMBRETE_NOVA_TENTATIVA)


def test_json_invalido_duas_vezes_vira_erro_claro():
    servidor = Servidor(_resposta_ok("{ruim"), _resposta_ok('{"queixas": "fora"}'))
    with pytest.raises(ErroLLM) as erro:
        _gerar(_cliente(servidor))
    assert erro.value.mensagem == MENSAGEM_PADRAO
    assert len(servidor.pedidos) == 2


# ---------- cadeia de modelos ----------


def test_cota_esgotada_passa_para_o_proximo_modelo():
    servidor = Servidor(_erro(429, "RESOURCE_EXHAUSTED"), _resposta_ok(VALIDO))
    cliente = _cliente(servidor)
    assert _gerar(cliente).queixas == ["dor-toracica"]
    assert servidor.modelos() == ["modelo-a", "modelo-b"]
    assert cliente.ultimo_modelo == "modelo-b"


def test_modelo_inexistente_passa_direto_para_o_proximo():
    servidor = Servidor(_erro(404, "NOT_FOUND"), _resposta_ok(VALIDO))
    assert _gerar(_cliente(servidor)).queixas == ["dor-toracica"]
    assert servidor.modelos() == ["modelo-a", "modelo-b"]


@pytest.mark.parametrize("status_http, status", [(500, "INTERNAL"), (503, "UNAVAILABLE")])
def test_sobrecarga_tenta_o_mesmo_modelo_mais_uma_vez(status_http, status):
    servidor = Servidor(_erro(status_http, status), _resposta_ok(VALIDO))
    cliente = _cliente(servidor)
    assert _gerar(cliente).queixas == ["dor-toracica"]
    assert servidor.modelos() == ["modelo-a", "modelo-a"]
    assert cliente.ultimo_modelo == "modelo-a"


@pytest.mark.parametrize("status_http, status", [(500, "INTERNAL"), (503, "UNAVAILABLE")])
def test_sobrecarga_duas_vezes_passa_para_o_proximo(status_http, status):
    servidor = Servidor(_erro(status_http, status), _erro(status_http, status), _resposta_ok(VALIDO))
    assert _gerar(_cliente(servidor)).queixas == ["dor-toracica"]
    assert servidor.modelos() == ["modelo-a", "modelo-a", "modelo-b"]


def test_todos_sem_cota_vira_mensagem_de_cota():
    servidor = Servidor(_erro(429, "RESOURCE_EXHAUSTED"), _erro(429, "RESOURCE_EXHAUSTED"))
    cliente = _cliente(servidor)
    with pytest.raises(ErroLLM) as erro:
        _gerar(cliente)
    assert erro.value.mensagem == MENSAGEM_COTA
    assert len(servidor.pedidos) == 2  # erro do provedor não ganha a nova tentativa do JSON
    assert cliente.ultimo_erro is not None
    assert (cliente.ultimo_erro.modelo, cliente.ultimo_erro.status_http) == ("modelo-b", 429)


def _cota(quota_id: str) -> httpx.Response:
    detalhes = [
        {
            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
            "violations": [{"quotaMetric": "generate_content_free_tier_requests", "quotaId": quota_id}],
        },
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "30s"},
    ]
    corpo = {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED", "details": detalhes}}
    return httpx.Response(429, json=corpo)


def test_cota_do_dia_em_todos_avisa_que_volta_amanha():
    servidor = Servidor(_cota("GenerateRequestsPerDayPerProjectPerModel-FreeTier"), _cota("RequestsPerDay-FreeTier"))
    cliente = _cliente(servidor)
    with pytest.raises(ErroLLM) as erro:
        _gerar(cliente)
    assert erro.value.mensagem == MENSAGEM_COTA_DIA
    assert cliente.ultimo_erro.cota_do_dia


def test_cota_por_minuto_em_algum_modelo_pede_para_tentar_mais_tarde():
    servidor = Servidor(_cota("GenerateRequestsPerDayPerProjectPerModel-FreeTier"), _cota("RequestsPerMinute-FreeTier"))
    with pytest.raises(ErroLLM) as erro:
        _gerar(_cliente(servidor))
    assert erro.value.mensagem == MENSAGEM_COTA


def test_cota_vale_mais_que_o_erro_do_ultimo_modelo():
    servidor = Servidor(_erro(429, "RESOURCE_EXHAUSTED"), httpx.ReadTimeout("devagar"))
    with pytest.raises(ErroLLM) as erro:
        _gerar(_cliente(servidor))
    assert erro.value.mensagem == MENSAGEM_COTA


def test_ultimo_erro_e_limpo_a_cada_chamada():
    servidor = Servidor(_erro(429, "RESOURCE_EXHAUSTED"), _resposta_ok(VALIDO), _resposta_ok(VALIDO, parada="SAFETY"))
    cliente = _cliente(servidor)
    _gerar(cliente)
    with pytest.raises(ErroLLM):
        _gerar(cliente)
    assert cliente.ultimo_erro.status_http == 200
    assert cliente.ultimo_erro.codigo == "SAFETY"


@pytest.mark.parametrize("excecao", [httpx.ConnectTimeout("x"), httpx.PoolTimeout("x"), httpx.ConnectError("x")])
def test_sem_conexao_nao_percorre_a_cadeia(excecao):
    servidor = Servidor(excecao)
    with pytest.raises(ErroLLM) as erro:
        _gerar(_cliente(servidor))
    assert erro.value.mensagem == MENSAGEM_SEM_CONEXAO
    assert len(servidor.pedidos) == 1


def test_resposta_comprimida_quebrada_vira_erro_llm():
    servidor = Servidor(
        httpx.Response(200, headers={"content-encoding": "gzip"}, stream=httpx.ByteStream(b"nao e gzip"))
    )
    with pytest.raises(ErroLLM):
        _gerar(_cliente(servidor))


def test_pedido_invalido_nao_tenta_outro_modelo():
    servidor = Servidor(_erro(400, "INVALID_ARGUMENT", "schema ruim"))
    cliente = _cliente(servidor)
    with pytest.raises(ErroLLM) as erro:
        _gerar(cliente)
    assert erro.value.mensagem == MENSAGEM_PADRAO
    assert len(servidor.pedidos) == 1
    assert cliente.ultimo_erro.mensagem == "schema ruim"


def test_chave_invalida_guarda_o_motivo():
    servidor = Servidor(_erro(400, "INVALID_ARGUMENT", "API key not valid", motivo="API_KEY_INVALID"))
    cliente = _cliente(servidor)
    with pytest.raises(ErroLLM):
        _gerar(cliente)
    assert cliente.ultimo_erro.codigo == "INVALID_ARGUMENT/API_KEY_INVALID"


def test_tempo_esgotado_tenta_o_proximo():
    servidor = Servidor(httpx.ReadTimeout("devagar"), _resposta_ok(VALIDO))
    assert _gerar(_cliente(servidor)).queixas == ["dor-toracica"]


def test_tempo_esgotado_em_todos_vira_sem_conexao():  # demora na resposta, não na conexão
    servidor = Servidor(httpx.ReadTimeout("devagar"), httpx.ReadTimeout("devagar"))
    with pytest.raises(ErroLLM) as erro:
        _gerar(_cliente(servidor))
    assert erro.value.mensagem == MENSAGEM_SEM_CONEXAO


def test_sem_internet_para_na_hora():
    servidor = Servidor(httpx.ConnectError("sem rede"))
    with pytest.raises(ErroLLM) as erro:
        _gerar(_cliente(servidor))
    assert erro.value.mensagem == MENSAGEM_SEM_CONEXAO
    assert len(servidor.pedidos) == 1


# ---------- respostas sem texto útil ----------


@pytest.mark.parametrize(
    "resposta, mensagem",
    [
        (_resposta_ok(VALIDO, parada="SAFETY"), MENSAGEM_RECUSA),
        (_resposta_ok(VALIDO, parada="RECITATION"), MENSAGEM_RECUSA),
        (_resposta_ok('{"queixas": [', parada="MAX_TOKENS"), MENSAGEM_LONGA),
        (httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}), MENSAGEM_RECUSA),
        (httpx.Response(200, json={"candidates": []}), MENSAGEM_PADRAO),
        (_resposta_ok("", partes=[{"text": "  "}]), MENSAGEM_PADRAO),
        (httpx.Response(200, text="<html>não é json</html>"), MENSAGEM_PADRAO),
        (httpx.Response(200, json=[1, 2]), MENSAGEM_PADRAO),
        (httpx.Response(200, json={"candidates": ["texto solto"]}), MENSAGEM_PADRAO),
        (_resposta_ok(VALIDO, parada="LANGUAGE"), MENSAGEM_RECUSA),
        (_resposta_ok("", parada="PUP_LIMITED_DISABLED", partes=[]), MENSAGEM_CONTA),
    ],
)
def test_resposta_sem_json_vira_erro_claro(resposta, mensagem):
    servidor = Servidor(resposta)
    with pytest.raises(ErroLLM) as erro:
        _gerar(_cliente(servidor))
    assert erro.value.mensagem == mensagem
    assert len(servidor.pedidos) == 1


def test_sem_chave_nao_chama_a_api():
    servidor = Servidor()
    http = httpx.Client(base_url="https://gemini.teste/v1beta", transport=httpx.MockTransport(servidor))
    cliente = ClienteGemini(_settings(gemini_api_key=None), client=http)
    with pytest.raises(ErroLLM) as erro:
        _gerar(cliente)
    assert erro.value.mensagem == MENSAGEM_SEM_CHAVE
    assert servidor.pedidos == []


# ---------- privacidade ----------


def test_log_nao_leva_conteudo_nem_chave(caplog):
    caplog.set_level(logging.DEBUG)
    servidor = Servidor(
        _erro(429, "RESOURCE_EXHAUSTED", f"cota: {SEGREDO}"),
        _resposta_ok(SEGREDO, parada="SAFETY"),
    )
    with pytest.raises(ErroLLM):
        _gerar(_cliente(servidor), mensagem=SEGREDO)
    assert caplog.records  # houve log, só que sem conteúdo
    for registro in caplog.records:
        texto = registro.getMessage()
        assert SEGREDO not in texto
        assert "chave-de-teste" not in texto


# ---------- lista de modelos (python -m app.testar_ia --modelos) ----------


def test_lista_modelos_que_geram_texto_em_todas_as_paginas():
    from app.llm.gemini import listar_modelos

    pagina1 = {
        "models": [
            {"name": "models/modelo-a", "supportedGenerationMethods": ["generateContent", "countTokens"]},
            {"name": "models/so-embedding", "supportedGenerationMethods": ["embedContent"]},
        ],
        "nextPageToken": "p2",
    }
    pagina2 = {"models": [{"name": "models/modelo-b", "supportedGenerationMethods": ["generateContent"]}]}
    servidor = Servidor(httpx.Response(200, json=pagina1), httpx.Response(200, json=pagina2))
    http = httpx.Client(base_url="https://gemini.teste/v1beta", transport=httpx.MockTransport(servidor))
    assert listar_modelos(_settings(), client=http) == ["modelo-a", "modelo-b"]
    assert servidor.pedidos[1].url.params["pageToken"] == "p2"
    assert all(p.headers["x-goog-api-key"] == "chave-de-teste" for p in servidor.pedidos)
