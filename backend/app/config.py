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
    gemini_modelos_leves: str = "gemini-3.5-flash-lite"
    """Modelos para as tarefas mais simples (queixa, anamnese e sugestões), antes dos de
    `gemini_modelos`. Guarda a cota dos modelos melhores para separar as falas e corrigir.
    Vazio: todas as tarefas usam `gemini_modelos`."""
    gemini_temperatura: float | None = None
    """Temperatura do Gemini. Vazia: o padrão do modelo. Mais baixa dá correções mais parecidas
    entre si. Só vale para o Gemini: os modelos atuais da Claude não aceitam temperature."""

    # Transcrição
    transcricao: Literal["local", "api", "falso"] = "falso"
    whisper_modelo_local: str = "small"
    openai_api_key: SecretStr | None = None

    # Voz do paciente pela IA
    voz_paciente: Literal["navegador", "edge", "piper"] = "navegador"
    """navegador: o aparelho do aluno lê a resposta. edge: vozes neurais do Edge (internet).
    piper: o backend fala com o Piper, na máquina."""
    edge_voz_feminina: str = "pt-BR-FranciscaNeural"
    edge_voz_masculina: str = "pt-BR-AntonioNeural"
    piper_voz_masculina: Path | None = None
    piper_voz_feminina: Path | None = None
    """Arquivos .onnx das vozes do Piper (com o .onnx.json ao lado). Sem a voz de um sexo,
    o Piper usa a outra."""

    # Banco e login
    banco: Literal["memoria", "arquivo", "supabase"] = "memoria"
    """memoria some ao fechar o app; arquivo guarda o histórico num JSON no computador."""
    arquivo_historico: Path = Path("dados/historico.json")
    """Onde BANCO=arquivo guarda as sessões. Fica fora do git."""
    auth: Literal["dev", "supabase"] = "dev"
    supabase_url: str | None = None
    supabase_service_key: SecretStr | None = None

    # Correção
    contar_rascunho: bool = True
    """Rascunho entra na nota (marcada como provisória) enquanto nenhum checklist foi assinado."""
    correcao_itens_por_pedido: int = 0
    """Máximo de itens por pedido de correção ao LLM. 0: cada checklist vai inteiro num pedido.
    Pedidos menores ajudam modelos mais fracos a olhar item por item."""

    # Arquivos
    pasta_conteudo: Path = Path("../content")
    pasta_audio_temp: Path = Path(tempfile.gettempdir()) / "anamnelab-audio"

    # HTTP
    cors_origens: str = "http://localhost:5173"
    """Origens separadas por vírgula."""

    # Limites do áudio
    duracao_maxima_min: int = 20
    tamanho_maximo_mb: int = 25

    @field_validator("pasta_conteudo", "pasta_audio_temp", "piper_voz_masculina", "piper_voz_feminina")
    @classmethod
    def _relativo_ao_backend(cls, valor: Path | None) -> Path | None:
        if valor is None or str(valor).strip() in ("", "."):
            return None
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
    def lista_modelos_gemini_leves(self) -> list[str]:
        return [modelo.strip() for modelo in self.gemini_modelos_leves.split(",") if modelo.strip()]

    @property
    def tamanho_maximo_bytes(self) -> int:
        return self.tamanho_maximo_mb * 1024 * 1024


@lru_cache
def obter_settings() -> Settings:
    return Settings()
