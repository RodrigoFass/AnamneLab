"""Provedor Gemini (Google), pela API REST `generateContent`, com httpx.

Tem plano gratuito sem cartão (chave criada no Google AI Studio): serve para mostrar o
app com correção de verdade sem custo. No plano gratuito o Google pode guardar o conteúdo,
usar para melhorar os produtos dele e ter pessoas revisando; o termo avisa disso (desde a v2) e o
caso é sempre simulado.

Cada modelo tem a sua cota gratuita. `GEMINI_MODELOS` é uma lista em ordem: quando um
modelo esgota a cota (429), não existe (404) ou está sobrecarregado (5xx), tenta o
próximo. As tarefas simples (TAREFAS_LEVES) começam por `GEMINI_MODELOS_LEVES`, para
sobrar cota dos modelos melhores para separar as falas e corrigir. Nada do conteúdo
(transcrição, falas) vai para o log, só códigos de erro.
"""

import copy
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel

from app.config import Settings
from app.llm.base import MENSAGEM_PADRAO, ClienteLLM, ErroLLM, schema_para_llm

logger = logging.getLogger(__name__)

URL_BASE = "https://generativelanguage.googleapis.com/v1beta"
TEMPO_LIMITE_S = 180.0
TEMPOS = httpx.Timeout(TEMPO_LIMITE_S, connect=10.0, write=30.0, pool=10.0)
"""Só a leitura da resposta pode demorar (o modelo pensando); conectar não."""

MENSAGEM_SEM_CHAVE = "A correção por IA não está configurada: falta a chave do Gemini no servidor."
MENSAGEM_COTA = "O limite gratuito da correção por IA acabou por agora. Tente de novo mais tarde."
MENSAGEM_COTA_DIA = "O limite gratuito de hoje da correção por IA acabou. Ele volta amanhã."
MENSAGEM_CONTA = "A conta da correção por IA está bloqueada pelo Google. Avise quem cuida do app."
MENSAGEM_SEM_CONEXAO = "Não deu para falar com o serviço de correção. Confira a internet e tente de novo."
MENSAGEM_RECUSA = (
    "O serviço de correção não aceitou analisar esta gravação. "
    "Confira se a conversa é uma simulação de anamnese e tente de novo."
)
MENSAGEM_LONGA = "A conversa ficou longa demais para corrigir de uma vez. Tente uma gravação mais curta."

PASSAR_AO_PROXIMO = {404, 429, 500, 502, 503, 504}
"""Erros em que outro modelo da lista pode dar certo (cota, nome, sobrecarga)."""
TENTAR_DE_NOVO = {500, 502, 503, 504}
"""Sobrecarga passageira: o mesmo modelo ganha mais uma chance antes do próximo da lista,
que costuma ser mais fraco (o flash-lite corrige pior)."""
ESPERA_NOVA_TENTATIVA_S = 2.0
ESPERA_MAXIMA_COTA_S = 20.0
"""Cota por minuto (429 que não é do dia): se o Google pede para esperar até isso, o mesmo
modelo ganha mais uma chance depois da espera, em vez de cair para um modelo mais fraco."""

TAREFAS_LEVES = {"queixa", "anamnese", "sugestoes", "paciente_caso", "paciente_resposta"}
"""Tarefas em que um modelo mais simples basta. Separar as falas e corrigir pedem o melhor."""

PARADA_RECUSA = {
    "SAFETY",
    "RECITATION",
    "BLOCKLIST",
    "PROHIBITED_CONTENT",
    "SPII",
    "IMAGE_SAFETY",
    "IMAGE_PROHIBITED_CONTENT",
    "ESCALATION",
    "LANGUAGE",
}
PARADA_LIMITE = {"MAX_TOKENS"}
PARADA_CONTA = {"PUP_LIMITED_DISABLED"}


@dataclass
class ErroGemini:
    """Último erro da API, guardado em memória (nunca no log) para `python -m app.testar_ia`."""

    modelo: str
    status_http: int | None
    codigo: str | None
    mensagem: str
    cota_do_dia: bool = False
    cota: str | None = None
    """quotaId da cota que acabou, no 429 (ex.: "GenerateRequestsPerMinutePerProjectPerModel-FreeTier")."""
    espera_s: float | None = None
    """Quanto o Google pede para esperar antes de tentar de novo (RetryInfo), no 429."""


def schema_para_gemini(modelo: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema da saída sem `$ref`: as definições de `$defs` entram no lugar.

    O Gemini aceita JSON Schema em `responseJsonSchema`, mas referências a `$defs` não são
    garantidas; os modelos de saída não são recursivos, então dá para expandir tudo.
    """
    schema = schema_para_llm(modelo)
    definicoes: dict[str, Any] = schema.pop("$defs", {})

    def expandir(no: Any, caminho: tuple[str, ...]) -> Any:
        if isinstance(no, dict):
            ref = no.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                nome = ref.removeprefix("#/$defs/")
                if nome in caminho:
                    raise ValueError(f"schema recursivo não suportado: {nome}")
                alvo = copy.deepcopy(definicoes[nome])
                extras = {k: v for k, v in no.items() if k != "$ref"}
                return expandir({**alvo, **extras}, (*caminho, nome))
            return {chave: expandir(valor, caminho) for chave, valor in no.items()}
        if isinstance(no, list):
            return [expandir(valor, caminho) for valor in no]
        return no

    return expandir(schema, ())


class ClienteGemini(ClienteLLM):
    nome = "gemini"

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        chave = settings.gemini_api_key
        self._chave = chave.get_secret_value() if chave else None
        self._modelos = settings.lista_modelos_gemini
        leves = settings.lista_modelos_gemini_leves
        self._modelos_leves = leves + [m for m in self._modelos if m not in leves]
        self._client = client or httpx.Client(base_url=URL_BASE, timeout=TEMPOS)
        self.ultimo_erro: ErroGemini | None = None
        self.ultimo_modelo: str | None = None
        self.espera_nova_tentativa_s = ESPERA_NOVA_TENTATIVA_S
        self.dormir = time.sleep
        self._temperatura = settings.gemini_temperatura

    def modelos_da_tarefa(self, tarefa: str) -> list[str]:
        return self._modelos_leves if tarefa in TAREFAS_LEVES else self._modelos

    def _espera_para_tentar_de_novo(self, modelo: str) -> float | None:
        """Segundos até a segunda chance no mesmo modelo, ou None se é para passar ao próximo."""
        anterior = self.ultimo_erro
        if not anterior or anterior.modelo != modelo:
            return None
        if anterior.status_http in TENTAR_DE_NOVO:
            return self.espera_nova_tentativa_s
        if (
            anterior.status_http == 429
            and not anterior.cota_do_dia
            and anterior.espera_s is not None
            and anterior.espera_s <= ESPERA_MAXIMA_COTA_S
        ):
            return anterior.espera_s
        return None

    def _gerar_json(
        self,
        *,
        tarefa: str,
        sistema: str,
        mensagem: str,
        saida: type[BaseModel],
        contexto: dict[str, Any] | None,
    ) -> str:
        self.ultimo_erro = None
        self.ultimo_modelo = None
        if not self._chave:
            logger.warning("GEMINI_API_KEY ausente (tarefa=%s)", tarefa)
            raise ErroLLM(MENSAGEM_SEM_CHAVE)
        modelos = self.modelos_da_tarefa(tarefa)
        if not modelos:
            logger.warning("GEMINI_MODELOS vazio (tarefa=%s)", tarefa)
            raise ErroLLM(MENSAGEM_PADRAO)

        configuracao: dict[str, Any] = {
            "responseMimeType": "application/json",
            # `responseJsonSchema` está marcado como obsoleto em favor de `responseFormat`, mas
            # é o que os modelos atuais aceitam com certeza; trocar só testando com chave real.
            "responseJsonSchema": schema_para_gemini(saida),
        }
        if self._temperatura is not None:
            configuracao["temperature"] = self._temperatura
        corpo = {
            "systemInstruction": {"parts": [{"text": sistema}]},
            "contents": [{"role": "user", "parts": [{"text": mensagem}]}],
            "generationConfig": configuracao,
        }
        # A cota esgotada vale mais que o erro do último modelo: é o que o aluno precisa saber.
        cotas: list[ErroGemini] = []
        mensagem_final = MENSAGEM_PADRAO
        tentativas = [(modelo, vez) for modelo in modelos for vez in (1, 2)]
        for modelo, vez in tentativas:
            if vez == 2:
                # Segunda chance só depois de sobrecarga (5xx) ou de cota por minuto no mesmo modelo.
                espera = self._espera_para_tentar_de_novo(modelo)
                if espera is None:
                    continue
                self.dormir(espera)
            try:
                resposta = self._client.post(
                    f"/models/{modelo}:generateContent",
                    json=corpo,
                    headers={"x-goog-api-key": self._chave},
                )
            except (httpx.ConnectTimeout, httpx.PoolTimeout, httpx.ConnectError):
                logger.warning("sem conexão com o Gemini (tarefa=%s)", tarefa)
                self.ultimo_erro = ErroGemini(modelo, None, "SEM_CONEXAO", "sem conexão")
                raise ErroLLM(MENSAGEM_SEM_CONEXAO) from None
            except httpx.TimeoutException:
                logger.warning("Gemini demorou demais (tarefa=%s, modelo=%s)", tarefa, modelo)
                self.ultimo_erro = ErroGemini(modelo, None, "TIMEOUT", "tempo esgotado")
                mensagem_final = MENSAGEM_SEM_CONEXAO
                continue
            except httpx.HTTPError as erro:
                logger.warning("falha ao falar com o Gemini (tarefa=%s, erro=%s)", tarefa, type(erro).__name__)
                self.ultimo_erro = ErroGemini(modelo, None, type(erro).__name__, "falha de rede")
                raise ErroLLM(MENSAGEM_SEM_CONEXAO) from None

            if resposta.status_code == 200:
                self.ultimo_modelo = modelo
                logger.info("Gemini respondeu (tarefa=%s, modelo=%s)", tarefa, modelo)
                return self._ler_texto(resposta, tarefa=tarefa, modelo=modelo)

            erro = _ler_erro(resposta, modelo)
            self.ultimo_erro = erro
            # Só o código HTTP e o código do Google vão para o log, nunca a mensagem.
            logger.warning(
                "Gemini respondeu HTTP %s (%s) (tarefa=%s, modelo=%s, cota=%s, espera=%s)",
                erro.status_http,
                erro.codigo,
                tarefa,
                modelo,
                erro.cota,
                erro.espera_s,
            )
            if resposta.status_code in PASSAR_AO_PROXIMO:
                if resposta.status_code == 429:
                    cotas.append(erro)
                continue
            raise ErroLLM(MENSAGEM_PADRAO)

        if cotas:
            self.ultimo_erro = cotas[-1]
            # "Volta amanhã" só quando todos os modelos sem cota esgotaram a do dia.
            raise ErroLLM(MENSAGEM_COTA_DIA if all(c.cota_do_dia for c in cotas) else MENSAGEM_COTA)
        raise ErroLLM(mensagem_final)

    def _falhou(self, modelo: str, codigo: str, explicacao: str, mensagem: str) -> ErroLLM:
        """Guarda o motivo para o `testar_ia` (nunca no log) e devolve o erro para o aluno."""
        self.ultimo_erro = ErroGemini(modelo, 200, codigo, explicacao)
        return ErroLLM(mensagem)

    def _ler_texto(self, resposta: httpx.Response, *, tarefa: str, modelo: str) -> str:
        try:
            dados = resposta.json()
        except ValueError:
            dados = None
        if not isinstance(dados, dict):
            logger.warning("Gemini respondeu algo que não é um objeto JSON (tarefa=%s, modelo=%s)", tarefa, modelo)
            raise self._falhou(modelo, "RESPOSTA_ESTRANHA", "a resposta não é um objeto JSON", MENSAGEM_PADRAO)

        feedback = dados.get("promptFeedback")
        bloqueio = feedback.get("blockReason") if isinstance(feedback, dict) else None
        if bloqueio:
            logger.warning("Gemini bloqueou o pedido (tarefa=%s, motivo=%s)", tarefa, bloqueio)
            raise self._falhou(modelo, str(bloqueio), "pedido bloqueado", MENSAGEM_RECUSA)

        candidatos = dados.get("candidates")
        candidato = candidatos[0] if isinstance(candidatos, list) and candidatos else None
        if not isinstance(candidato, dict):
            logger.warning("Gemini respondeu sem candidatos (tarefa=%s, modelo=%s)", tarefa, modelo)
            raise self._falhou(modelo, "SEM_CANDIDATOS", "resposta sem candidatos", MENSAGEM_PADRAO)
        parada = candidato.get("finishReason")
        if parada in PARADA_RECUSA:
            logger.warning("Gemini recusou (tarefa=%s, motivo=%s)", tarefa, parada)
            raise self._falhou(modelo, str(parada), "o modelo recusou", MENSAGEM_RECUSA)
        if parada in PARADA_CONTA:
            logger.warning("Gemini recusou pela conta (tarefa=%s, motivo=%s)", tarefa, parada)
            raise self._falhou(modelo, str(parada), "a conta está limitada pelo Google", MENSAGEM_CONTA)
        if parada in PARADA_LIMITE:
            logger.warning("Gemini parou por limite (tarefa=%s, motivo=%s)", tarefa, parada)
            raise self._falhou(modelo, str(parada), "a resposta passou do limite de tamanho", MENSAGEM_LONGA)

        conteudo = candidato.get("content")
        partes = conteudo.get("parts") if isinstance(conteudo, dict) else None
        # Partes de raciocínio ("thought") não fazem parte da resposta.
        texto = "".join(str(p.get("text", "")) for p in partes or [] if isinstance(p, dict) and not p.get("thought"))
        if not texto.strip():
            logger.warning("Gemini respondeu sem texto (tarefa=%s, modelo=%s, parada=%s)", tarefa, modelo, parada)
            raise self._falhou(modelo, f"SEM_TEXTO/{parada}", "resposta sem texto", MENSAGEM_PADRAO)
        return texto


def _ler_erro(resposta: httpx.Response, modelo: str) -> ErroGemini:
    """Erro no formato do Google: {"error": {"code", "message", "status", "details": [...]}}.

    No 429, o detalhe QuotaFailure diz qual cota acabou; "PerDay" no quotaId é a do dia.
    """
    try:
        corpo = resposta.json()
    except ValueError:
        corpo = None
    erro = corpo.get("error") if isinstance(corpo, dict) else None
    if not isinstance(erro, dict):
        erro = {}
    codigo = erro.get("status")
    cota_do_dia = False
    cota = None
    espera = None
    for detalhe in erro.get("details") or []:
        if not isinstance(detalhe, dict):
            continue
        if detalhe.get("reason") and codigo == erro.get("status"):
            codigo = f"{codigo}/{detalhe['reason']}" if codigo else detalhe["reason"]
        for violacao in detalhe.get("violations") or []:
            if not isinstance(violacao, dict):
                continue
            quota_id = str(violacao.get("quotaId", ""))
            cota = cota or quota_id or None
            if "PerDay" in quota_id:
                cota_do_dia = True
                cota = quota_id
        espera = espera if espera is not None else _segundos(detalhe.get("retryDelay"))
    return ErroGemini(
        modelo,
        resposta.status_code,
        str(codigo) if codigo else None,
        str(erro.get("message") or resposta.reason_phrase),
        cota_do_dia,
        cota,
        espera,
    )


def _segundos(duracao: object) -> float | None:
    """Duração no formato do Google ("12s", "1.5s") em segundos; None se não der para ler."""
    if not isinstance(duracao, str) or not duracao.endswith("s"):
        return None
    try:
        segundos = float(duracao[:-1])
    except ValueError:
        return None
    return segundos if segundos >= 0 else None


def listar_modelos(settings: Settings, client: httpx.Client | None = None) -> list[str]:
    """Modelos que a chave acessa e que geram texto (`generateContent`), sem o prefixo "models/".

    Só para `python -m app.testar_ia --modelos`. Levanta ErroLLM sem chave ou se a API recusar.
    """
    chave = settings.gemini_api_key
    if not chave:
        raise ErroLLM(MENSAGEM_SEM_CHAVE)
    http = client or httpx.Client(base_url=URL_BASE, timeout=httpx.Timeout(30.0, connect=10.0))
    nomes: list[str] = []
    pagina: str | None = None
    while True:
        params = {"pageSize": "1000", **({"pageToken": pagina} if pagina else {})}
        try:
            resposta = http.get("/models", params=params, headers={"x-goog-api-key": chave.get_secret_value()})
        except httpx.HTTPError:
            raise ErroLLM(MENSAGEM_SEM_CONEXAO) from None
        if resposta.status_code != 200:
            erro = _ler_erro(resposta, "-")
            raise ErroLLM(f"A API recusou (HTTP {erro.status_http}, {erro.codigo}): {erro.mensagem}")
        dados = resposta.json()
        for modelo in dados.get("models") or []:
            if "generateContent" in (modelo.get("supportedGenerationMethods") or []):
                nomes.append(str(modelo.get("name", "")).removeprefix("models/"))
        pagina = dados.get("nextPageToken")
        if not pagina:
            return nomes
