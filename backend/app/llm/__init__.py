"""Clientes de LLM atrás de uma interface única (trocar de provedor não muda o pipeline)."""

from app.config import Settings
from app.llm.base import ClienteLLM, ErroLLM, gerar_validado, schema_para_llm

__all__ = ["ClienteLLM", "ErroLLM", "gerar_validado", "obter_cliente_llm", "schema_para_llm"]


def obter_cliente_llm(settings: Settings) -> ClienteLLM:
    if settings.llm_provedor == "anthropic":
        from app.llm.anthropic import ClienteAnthropic

        return ClienteAnthropic(settings)
    if settings.llm_provedor == "gemini":
        from app.llm.gemini import ClienteGemini

        return ClienteGemini(settings)
    from app.llm.falso import ClienteFalso

    return ClienteFalso()
