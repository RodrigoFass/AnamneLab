"""Modelos da sessão de treino e da API.

O frontend espelha estes modelos em frontend/src/api/tipos.ts. Mudou aqui,
muda lá.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.llm import AnamneseEstruturada, CasoPaciente, Fala, SugestoesIA

OrigemCaso = Literal["livro", "internet", "inventado", "cartao", "paciente_ia"]
Papel = Literal["medico", "paciente"]

StatusSessao = Literal[
    "criada",                 # sessão aberta, esperando consentimentos e áudio
    "conversando",            # paciente pela IA: o aluno está entrevistando por escrito
    "processando_audio",      # transcrevendo e separando falas
    "aguardando_queixa",      # aluno confirma a queixa (e pode corrigir a transcrição)
    "corrigindo",             # montando anamnese e correção
    "aguardando_hipoteses",   # aluno escreve as hipóteses antes de ver a correção
    "gerando_sugestoes",      # IA gera hipóteses sugeridas
    "concluida",
    "erro",
]

StatusItem = Literal["feito", "faltou"]
SexoPaciente = Literal["feminino", "masculino"]
FormaConsentimento = Literal["aceite", "declarado_pelo_dono"]
"""`aceite`: a pessoa leu e aceitou o termo. `declarado_pelo_dono`: o colega não aceita no app;
quem abriu a sessão aceitou um termo em que se compromete a avisá-lo antes de gravar, e o app
registra esse aviso na sessão."""


# ---------- entrada ----------


class SessaoCriar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origem_caso: OrigemCaso
    cartao_id: str | None = None


class ConsentimentoCriar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    papel: Papel
    nome_informado: str = Field(min_length=1, max_length=120)
    versao_termo: str
    aceito: Literal[True]
    forma: FormaConsentimento = "aceite"


class PerguntaPaciente(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto: str = Field(min_length=1, max_length=500)


class TranscricaoEditar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    falas: list[Fala]


class QueixaConfirmar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queixas: list[str] = Field(min_length=1)
    """Ids da biblioteca, ou ['outra']."""
    descricao_outra: str | None = None
    sexo_paciente: SexoPaciente | None = None
    """Sexo do paciente simulado. Sem o campo, fica o detectado; null é 'não sei'."""


class HipotesesAluno(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hipoteses: list[str] = Field(min_length=1, max_length=10)


class ContestacaoCriar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    motivo: str = Field(min_length=1, max_length=1000)
    trecho: str | None = None
    """Fala da transcrição que o aluno aponta como prova."""


# ---------- saída ----------


class Saude(BaseModel):
    """Resposta de GET /api/saude."""

    ok: bool
    modo_demonstracao: bool
    """True quando o LLM ou a transcrição são falsos: a interface avisa o aluno."""


class Termo(BaseModel):
    versao: str
    titulo: str
    texto: str


class Consentimento(BaseModel):
    id: str
    sessao_id: str
    papel: Papel
    nome_informado: str
    versao_termo: str
    aceito_em: datetime
    forma: FormaConsentimento = "aceite"


class ChecklistUsado(BaseModel):
    id: str
    versao: int
    status: Literal["rascunho", "aprovado"]
    conta_na_nota: bool


class Avaliacao(BaseModel):
    """Um item corrigido. O trecho só existe se foi conferido na transcrição."""

    item_id: str
    checklist_id: str
    secao: str
    texto: str
    status: StatusItem
    trecho: str | None
    mensagem: str
    """Feito: o que o aluno fez. Faltou: a frase 'faltou' do checklist."""
    peso: int
    conta_na_nota: bool
    contestacao: "Contestacao | None" = None


class Contestacao(BaseModel):
    item_id: str
    motivo: str
    trecho: str | None
    resultado: Literal["procedente", "pendente_professor"]
    criada_em: datetime


class Notas(BaseModel):
    geral: int | None
    """Técnica geral, 0 a 100. Nulo se o checklist geral não conta na nota."""
    queixa: int | None
    """Específica da queixa, 0 a 100. Nulo se não há checklist da queixa que conte."""
    provisoria: bool
    """True quando entrou checklist em rascunho na conta (CONTAR_RASCUNHO=true)."""


class Sessao(BaseModel):
    id: str
    dono_id: str
    criada_em: datetime
    status: StatusSessao
    progresso: int = 0
    """0 a 100, para a barra de progresso."""
    mensagem_erro: str | None = None
    origem_caso: OrigemCaso
    cartao_id: str | None = None
    consentimentos: list[Consentimento] = []
    falas: list[Fala] = []
    transcricao_editada: bool = False
    queixa_detectada: list[str] = []
    queixa_trecho: str | None = None
    queixas_confirmadas: list[str] = []
    descricao_outra: str | None = None
    sexo_paciente: SexoPaciente | None = None
    """Detectado na conversa e confirmado pelo aluno com a queixa. Item só de um sexo não vale para o outro."""
    checklists_usados: list[ChecklistUsado] = []
    anamnese: AnamneseEstruturada | None = None
    hipoteses_aluno: list[str] = []
    avaliacoes: list[Avaliacao] = []
    """Só é preenchido na resposta depois que o aluno enviou as hipóteses."""
    notas: Notas | None = None
    sugestoes: SugestoesIA | None = None
    caso_ia: CasoPaciente | None = None
    """Ficha do paciente pela IA (caso fictício). O aluno só vê depois de encerrar a conversa."""


class SessaoResumo(BaseModel):
    id: str
    criada_em: datetime
    status: StatusSessao
    queixas_confirmadas: list[str]
    notas: Notas | None


Avaliacao.model_rebuild()
