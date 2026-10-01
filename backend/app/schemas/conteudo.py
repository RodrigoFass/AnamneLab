"""Modelos do conteúdo em content/ (checklists, queixas e cartões).

Espelham os JSON Schemas de content/schema/. O validador de conteúdo usa os
JSON Schemas; o backend carrega com estes modelos.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class Fonte(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: Literal["livro", "web"]
    referencia: str
    pagina: str | None = None
    url: str | None = None


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    texto: str
    pergunta_exemplo: str | None = None
    faltou: str
    peso: int
    palavras_chave: list[str] = []
    fonte: Fonte


class Secao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    titulo: str
    itens: list[Item]


class Checklist(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    nome: str
    tipo: Literal["geral", "queixa"]
    queixa: str | None
    versao: int
    status: Literal["rascunho", "aprovado"]
    origem: Literal["fontes-publicas", "livros"]
    validado_por: str | None
    validado_em: date | None
    observacoes: str | None = None
    secoes: list[Secao]

    @model_validator(mode="after")
    def _assinatura(self) -> "Checklist":
        if self.status == "aprovado" and not (self.validado_por and self.validado_em):
            raise ValueError("checklist aprovado precisa de validado_por e validado_em")
        return self

    @property
    def itens(self) -> list[Item]:
        return [item for secao in self.secoes for item in secao.itens]

    @property
    def aprovado(self) -> bool:
        return self.status == "aprovado"


class Queixa(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    nome: str
    sinonimos: list[str]
    checklist: str | None


class BibliotecaQueixas(BaseModel):
    model_config = ConfigDict(extra="forbid")

    versao: int
    queixas: list[Queixa]


class Cartao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    queixa: str
    idade: int
    sexo: Literal["feminino", "masculino"]
    resumo: str
    detalhes: list[str]


class BibliotecaCartoes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    versao: int
    cartoes: list[Cartao]
