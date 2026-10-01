from pathlib import Path

import pytest

from app.config import Settings
from app.conteudo import Conteudo, carregar_conteudo
from tests.apoio import PASTA_FIXTURES


@pytest.fixture
def pasta_conteudo() -> Path:
    return PASTA_FIXTURES


@pytest.fixture
def conteudo() -> Conteudo:
    return carregar_conteudo(PASTA_FIXTURES)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Configuração isolada: sem .env, tudo falso e em memória, áudio numa pasta do teste."""
    return Settings(
        _env_file=None,
        llm_provedor="falso",
        transcricao="falso",
        banco="memoria",
        auth="dev",
        contar_rascunho=True,
        pasta_conteudo=PASTA_FIXTURES,
        pasta_audio_temp=tmp_path / "audio",
        tamanho_maximo_mb=25,
    )
