"""Peças comuns às etapas do pipeline."""

from typing import Any

from app.schemas.llm import Fala

ROTULOS = {"entrevistador": "Entrevistador", "paciente": "Paciente"}


class ErroPipeline(Exception):
    """Falha esperada numa etapa. `mensagem` é mostrada ao aluno, em tom de preceptor."""

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


def formatar_falas(falas: list[Fala]) -> str:
    """Transcrição para o prompt, uma fala por linha com o papel na frente."""
    return "\n".join(f"{ROTULOS[f.papel]}: {f.texto}" for f in falas)


def falas_para_contexto(falas: list[Fala]) -> list[dict[str, Any]]:
    return [f.model_dump() for f in falas]
