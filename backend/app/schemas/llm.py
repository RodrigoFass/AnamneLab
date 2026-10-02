"""Saídas do LLM. Todo JSON que volta do modelo é validado por um destes.

Regras para estes modelos:
- `extra="forbid"` em todos (o JSON Schema gerado sai com additionalProperties false,
  como a saída estruturada exige).
- Só tipos simples (str, bool, int, list, Literal, modelos aninhados) para o schema
  ser aceito pela saída estruturada dos provedores.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Fala(BaseModel):
    model_config = ConfigDict(extra="forbid")

    papel: Literal["entrevistador", "paciente"]
    texto: str


class FalasRotuladas(BaseModel):
    """Saída de rotular_falas: a transcrição separada por quem falou."""

    model_config = ConfigDict(extra="forbid")

    falas: list[Fala]


class QueixaDetectada(BaseModel):
    """Saída de queixa: ids da lista fechada, ou 'outra'."""

    model_config = ConfigDict(extra="forbid")

    queixas: list[str]
    """Ids de content/queixas.json, na ordem de importância. ['outra'] se nada servir."""
    descricao_outra: str | None
    """Quando 'outra': a queixa como o paciente disse, curta."""
    trecho: str
    """Fala do paciente que mostra a queixa principal, copiada literalmente."""
    sexo_paciente: Literal["feminino", "masculino"] | None
    """Sexo do paciente simulado, pelo que a conversa mostra. Null se não der para saber."""


class AnamneseEstruturada(BaseModel):
    """Saída de anamnese. Campo não abordado na conversa vem como 'Não abordado.'"""

    model_config = ConfigDict(extra="forbid")

    identificacao: str
    queixa_principal: str
    hda: str
    interrogatorio_sintomatologico: str
    antecedentes_pessoais: str
    antecedentes_familiares: str
    habitos_de_vida: str
    condicoes_socioeconomicas: str


class ItemCorrigido(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    feito: bool
    falas: list[int]
    """Números das falas que provam o item, como aparecem na transcrição enviada: a pergunta
    do entrevistador e, se ajudar, a resposta logo depois. Vazia se não feito."""
    citacao: str | None
    """O pedaço curto dessas falas que mostra o item, copiado como está. Só para mostrar ao
    aluno: se não estiver nas falas citadas, o app mostra as falas inteiras."""


class CorrecaoLLM(BaseModel):
    """Saída de corrigir: um registro por item do checklist enviado."""

    model_config = ConfigDict(extra="forbid")

    itens: list[ItemCorrigido]


class TrechoCumpreItem(BaseModel):
    """Saída de verificar_contestacao: o trecho apontado pelo aluno mostra o item?"""

    model_config = ConfigDict(extra="forbid")

    cumpre: bool


class HipoteseIA(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str
    a_favor: list[str]
    contra: list[str]


class SugestoesIA(BaseModel):
    """Hipóteses sugeridas para estudo (nunca diagnóstico) e perguntas que ajudariam.

    `perguntas_sugeridas` cobre a terceira camada da correção: só existe quando alguma
    queixa confirmada é "outra" ou não tem checklist. Nos outros casos o backend devolve
    a lista vazia. Fica fora da nota.
    """

    model_config = ConfigDict(extra="forbid")

    hipoteses: list[HipoteseIA]
    perguntas_sugeridas: list[str]


# ---------- paciente pela IA ----------


class CasoPaciente(BaseModel):
    """Ficha do paciente simulado que a IA interpreta. Caso fictício, montado a partir de um cartão."""

    model_config = ConfigDict(extra="forbid")

    nome: str
    idade: int
    sexo: Literal["feminino", "masculino"]
    profissao: str
    queixa_nas_palavras_dele: str
    historia_da_doenca: list[str]
    """Fatos da doença atual, um por linha: início, local, tipo, intensidade, piora, melhora, sintomas juntos."""
    antecedentes: list[str]
    medicacoes: list[str]
    alergias: list[str]
    habitos: list[str]
    familia: list[str]
    vida_social: list[str]
    jeito_de_falar: str


class RespostaPaciente(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resposta: str
