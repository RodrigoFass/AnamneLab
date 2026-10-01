"""Interface única dos provedores de LLM.

O pipeline só conhece `ClienteLLM.gerar`. A regra 7 (saída validada pelo Pydantic,
uma nova tentativa em JSON inválido e depois erro claro ao aluno) vive aqui, em
`gerar_validado`, e não em cada provedor.
"""

import copy
import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

MENSAGEM_PADRAO = "Não deu para montar a correção agora. Tente de novo em alguns minutos."

LEMBRETE_NOVA_TENTATIVA = (
    "\n\nAtenção: a resposta anterior não seguiu o formato pedido. "
    "Responda só com o JSON no formato do schema, sem texto fora dele."
)


class ErroLLM(Exception):
    """Falha ao obter uma resposta válida do LLM. `mensagem` é mostrada ao aluno."""

    def __init__(self, mensagem: str = MENSAGEM_PADRAO) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


class ClienteLLM(ABC):
    """Um provedor de LLM. Os provedores só implementam `_gerar_json`."""

    nome: str = "base"

    def gerar[T: BaseModel](
        self,
        *,
        tarefa: str,
        sistema: str,
        mensagem: str,
        saida: type[T],
        contexto: dict[str, Any] | None = None,
    ) -> T:
        """Pede ao provedor uma resposta no formato `saida` e devolve o modelo validado.

        `contexto` leva dados estruturados (falas, itens, queixas). Provedores reais
        ignoram; o provedor falso usa para responder sem chamar ninguém.
        """
        return gerar_validado(self, tarefa=tarefa, sistema=sistema, mensagem=mensagem, saida=saida, contexto=contexto)

    @abstractmethod
    def _gerar_json(
        self,
        *,
        tarefa: str,
        sistema: str,
        mensagem: str,
        saida: type[BaseModel],
        contexto: dict[str, Any] | None,
    ) -> str:
        """Devolve o texto JSON cru da resposta. Levanta ErroLLM em falha do provedor."""


def gerar_validado[T: BaseModel](
    cliente: ClienteLLM,
    *,
    tarefa: str,
    sistema: str,
    mensagem: str,
    saida: type[T],
    contexto: dict[str, Any] | None = None,
) -> T:
    """Regra 7: valida com Pydantic; JSON inválido ganha uma nova tentativa, depois ErroLLM."""
    for tentativa in (1, 2):
        texto_mensagem = mensagem if tentativa == 1 else mensagem + LEMBRETE_NOVA_TENTATIVA
        texto = cliente._gerar_json(
            tarefa=tarefa, sistema=sistema, mensagem=texto_mensagem, saida=saida, contexto=contexto
        )
        try:
            return saida.model_validate_json(texto)
        except ValidationError:
            # Só a tarefa e a tentativa vão para o log, nunca o conteúdo.
            logger.warning("resposta do LLM fora do formato (tarefa=%s, tentativa=%d)", tarefa, tentativa)
    raise ErroLLM(MENSAGEM_PADRAO)


def schema_para_llm(modelo: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema do modelo para a saída estruturada.

    Garante `additionalProperties: false` em todo objeto (os modelos já usam
    extra="forbid") e mantém os `$defs` como estão.
    """
    schema = copy.deepcopy(modelo.model_json_schema())

    def fechar(no: Any) -> None:
        if isinstance(no, dict):
            if no.get("type") == "object":
                no["additionalProperties"] = False
            for chave, valor in no.items():
                if chave in ("properties", "$defs") and isinstance(valor, dict):
                    # Mapas de nome -> schema: o mapa em si não é um schema.
                    for sub in valor.values():
                        fechar(sub)
                else:
                    fechar(valor)
        elif isinstance(no, list):
            for valor in no:
                fechar(valor)

    fechar(schema)
    return schema
