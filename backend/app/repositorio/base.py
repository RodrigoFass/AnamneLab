"""Interface do repositório. O resto do app não sabe se o banco é memória ou Supabase."""

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.llm import Fala
from app.schemas.sessao import Avaliacao, Consentimento, Sessao

CAMPOS_SESSAO = frozenset(
    {
        "status",
        "progresso",
        "mensagem_erro",
        "queixa_detectada",
        "queixa_trecho",
        "queixas_confirmadas",
        "descricao_outra",
        "sexo_paciente",
        "caso_ia",
        "checklists_usados",
        "anamnese",
        "hipoteses_aluno",
        "notas",
        "sugestoes",
    }
)
"""Campos da tabela sessoes que mudam depois da criação."""


class Repositorio(ABC):
    @abstractmethod
    def criar_sessao(self, sessao: Sessao) -> None: ...

    @abstractmethod
    def obter_sessao(self, sessao_id: str) -> Sessao | None:
        """Sessão completa: consentimentos, falas e avaliações juntos."""

    @abstractmethod
    def listar_sessoes(self, dono_id: str) -> list[Sessao]:
        """Sessões do dono, mais recente primeiro. Falas e avaliações podem vir vazias."""

    @abstractmethod
    def atualizar_sessao(self, sessao_id: str, **campos: Any) -> None:
        """Atualiza só os campos de CAMPOS_SESSAO."""

    @abstractmethod
    def salvar_transcricao(self, sessao_id: str, falas: list[Fala], editada: bool) -> None: ...

    @abstractmethod
    def salvar_avaliacoes(self, sessao_id: str, avaliacoes: list[Avaliacao]) -> None:
        """Substitui todas as avaliações da sessão."""

    @abstractmethod
    def adicionar_consentimento(self, consentimento: Consentimento) -> None: ...

    @abstractmethod
    def apagar_sessao(self, sessao_id: str) -> None:
        """Apaga sessão, transcrição, avaliações e consentimentos."""

    @abstractmethod
    def registrar_queixa_outra(self, descricao: str) -> None:
        """Fila de queixas: soma 1 na frequência da descrição normalizada."""


def conferir_campos(campos: dict[str, Any]) -> None:
    desconhecidos = set(campos) - CAMPOS_SESSAO
    if desconhecidos:
        raise ValueError(f"campos que não podem ser atualizados: {sorted(desconhecidos)}")
