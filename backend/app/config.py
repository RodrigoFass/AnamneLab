"""Configuração do backend, lida do ambiente e de backend/.env.

Segredos (chaves de API, service key do Supabase) só entram por aqui, nunca no código.
"""

import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PASTA_BACKEND = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PASTA_BACKEND / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # IA de correção
    llm_provedor: Literal["anthropic", "gemini", "falso"] = "falso"
    llm_modelo: str = "claude-opus-5-5"
    llm_esforco: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    anthropic_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    gemini_modelos: str = "gemini-3.8-flash,gemini-3.5-flash,gemini-3.5-flash-lite"
    """Modelos do Gemini em ordem, separados por vírgula: se um esgota a cota grátis, tenta o próximo."""

    # Transcrição
    transcricao: Literal["local", "api", "falso"] = "falso"
    whisper_modelo_local: str = "small"
    openai_api_key: SecretStr | None = None

    # Banco e login
    banco: Literal["memoria", "supabase"] = "memoria"
    auth: Literal["dev", "supabase"] = "dev"
    supabase_url: str | None = None
    supabase_service_key: SecretStr | None = None

    # Correção
    contar_rascunho: bool = True
    """Rascunho entra na nota (marcada como provisória) enquanto nenhum checklist foi assinado."""

    # Arquivos
    pasta_conteudo: Path = Path("../content")
    pasta_audio_temp: Path = Path(tempfile.gettempdir()) / "anamnelab-audio"

    # HTTP
    cors_origens: str = "http://localhost:5173"
    """Origens separadas por vírgula."""

    # Limites do áudio
    duracao_maxima_min: int = 20
    tamanho_maximo_mb: int = 25

    @field_validator("pasta_conteudo", "pasta_audio_temp")
    @classmethod
    def _relativo_ao_backend(cls, valor: Path) -> Path:
        valor = Path(valor).expanduser()
        if not valor.is_absolute():
            valor = PASTA_BACKEND / valor
        return valor.resolve()

    @property
    def lista_cors(self) -> list[str]:
        return [origem.strip() for origem in self.cors_origens.split(",") if origem.strip()]

    @property
    def lista_modelos_gemini(self) -> list[str]:
        return [modelo.strip() for modelo in self.gemini_modelos.split(",") if modelo.strip()]

    @property
    def tamanho_maximo_bytes(self) -> int:
        return self.tamanho_maximo_mb * 1024 * 1024


@lru_cache
def obter_settings() -> Settings:
    return Settings()
