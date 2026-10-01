"""Provedor Anthropic, pelo SDK oficial.

Os modelos atuais não aceitam temperature/top_p: a regra "temperatura baixa" vira
saída estruturada (json_schema) + validação Pydantic + uma nova tentativa (em base.py).
Nada do conteúdo (transcrição, falas) vai para o log.
"""

import logging
from typing import Any

import anthropic
from pydantic import BaseModel

from app.config import Settings
from app.llm.base import MENSAGEM_PADRAO, ClienteLLM, ErroLLM, schema_para_llm

logger = logging.getLogger(__name__)

MAX_TOKENS = 16000
BETA_FALLBACK = "server-side-fallback-2026-07-01"

MENSAGEM_OCUPADO = "Muita gente corrigindo ao mesmo tempo. Tente de novo em alguns minutos."
MENSAGEM_SEM_CONEXAO = "Não deu para falar com o serviço de correção. Confira a internet e tente de novo."
MENSAGEM_RECUSA = (
    "O serviço de correção não aceitou analisar esta gravação. "
    "Confira se a conversa é uma simulação de anamnese e tente de novo."
)
MENSAGEM_LONGA = "A conversa ficou longa demais para corrigir de uma vez. Tente uma gravação mais curta."


class ClienteAnthropic(ClienteLLM):
    nome = "anthropic"

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._modelo = settings.llm_modelo
        self._esforco = settings.llm_esforco
        if client is None:
            chave = settings.anthropic_api_key
            client = anthropic.Anthropic(api_key=chave.get_secret_value() if chave else None)
        self._client = client

    def _gerar_json(
        self,
        *,
        tarefa: str,
        sistema: str,
        mensagem: str,
        saida: type[BaseModel],
        contexto: dict[str, Any] | None,
    ) -> str:
        try:
            resposta = self._client.beta.messages.create(
                model=self._modelo,
                max_tokens=MAX_TOKENS,
                system=sistema,
                messages=[{"role": "user", "content": mensagem}],
                output_config={
                    "format": {"type": "json_schema", "schema": schema_para_llm(saida)},
                    "effort": self._esforco,
                },
                betas=[BETA_FALLBACK],
                fallbacks="default",
            )
        except anthropic.RateLimitError:
            logger.warning("LLM limitou a taxa (tarefa=%s)", tarefa)
            raise ErroLLM(MENSAGEM_OCUPADO) from None
        except anthropic.APIStatusError as erro:
            logger.warning("LLM respondeu com erro HTTP %s (tarefa=%s)", erro.status_code, tarefa)
            raise ErroLLM(MENSAGEM_PADRAO) from None
        except anthropic.APIConnectionError:
            logger.warning("sem conexão com o LLM (tarefa=%s)", tarefa)
            raise ErroLLM(MENSAGEM_SEM_CONEXAO) from None

        # Confere o motivo da parada antes de ler o conteúdo.
        if resposta.stop_reason == "refusal":
            categoria = getattr(getattr(resposta, "stop_details", None), "category", None)
            logger.warning("LLM recusou (tarefa=%s, categoria=%s)", tarefa, categoria)
            raise ErroLLM(MENSAGEM_RECUSA)
        if resposta.stop_reason in ("max_tokens", "model_context_window_exceeded"):
            logger.warning("LLM parou por limite (tarefa=%s, motivo=%s)", tarefa, resposta.stop_reason)
            raise ErroLLM(MENSAGEM_LONGA)

        texto = next((bloco.text for bloco in resposta.content if bloco.type == "text"), None)
        if texto is None:
            logger.warning("LLM respondeu sem bloco de texto (tarefa=%s)", tarefa)
            raise ErroLLM(MENSAGEM_PADRAO)
        return texto
