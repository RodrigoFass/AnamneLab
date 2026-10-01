"""Ajudantes dos testes."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.llm.base import ClienteLLM
from app.schemas.llm import Fala

PASTA_FIXTURES = Path(__file__).parent / "fixtures" / "content"


class LLMFixo(ClienteLLM):
    """Provedor que devolve respostas prontas, na ordem, e guarda as chamadas."""

    nome = "fixo"

    def __init__(self, *respostas: str | dict[str, Any]) -> None:
        self.respostas = [r if isinstance(r, str) else json.dumps(r, ensure_ascii=False) for r in respostas]
        self.chamadas: list[dict[str, Any]] = []

    def _gerar_json(
        self,
        *,
        tarefa: str,
        sistema: str,
        mensagem: str,
        saida: type[BaseModel],
        contexto: dict[str, Any] | None,
    ) -> str:
        self.chamadas.append({"tarefa": tarefa, "mensagem": mensagem, "contexto": contexto})
        return self.respostas.pop(0)


def falas_exemplo() -> list[Fala]:
    return [
        Fala(papel="entrevistador", texto="Bom dia! Qual é o seu nome?"),
        Fala(papel="paciente", texto="Carlos Alberto."),
        Fala(papel="entrevistador", texto="Quantos anos o senhor tem?"),
        Fala(papel="paciente", texto="Cinquenta e oito."),
        Fala(papel="entrevistador", texto="Essa dor vai para algum outro lugar?"),
        Fala(papel="paciente", texto="Vai para o braço esquerdo."),
        Fala(papel="entrevistador", texto="O senhor fuma?"),
        Fala(papel="paciente", texto="Fumo um maço por dia, sim."),
        Fala(papel="entrevistador", texto="Suou frio junto com a dor?"),
        Fala(papel="paciente", texto="Não, suor não."),
    ]
