"""Dependências do app reunidas num lugar: configuração, conteúdo, LLM, transcrição e banco."""

from dataclasses import dataclass

from app.config import Settings
from app.conteudo import Conteudo, obter_conteudo
from app.llm import ClienteLLM, obter_cliente_llm
from app.pipeline.transcrever import Transcritor, obter_transcritor
from app.repositorio import Repositorio, obter_repositorio


@dataclass
class Servicos:
    settings: Settings
    llm: ClienteLLM
    transcritor: Transcritor
    repositorio: Repositorio

    @property
    def conteudo(self) -> Conteudo:
        return obter_conteudo(self.settings.pasta_conteudo)


def montar_servicos(
    settings: Settings,
    *,
    llm: ClienteLLM | None = None,
    transcritor: Transcritor | None = None,
    repositorio: Repositorio | None = None,
) -> Servicos:
    return Servicos(
        settings=settings,
        llm=llm or obter_cliente_llm(settings),
        transcritor=transcritor or obter_transcritor(settings),
        repositorio=repositorio or obter_repositorio(settings),
    )
