"""Esquemas do painel de atividade (só para quem está em ADMIN_EMAILS)."""

from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.sessao import OrigemCaso, StatusSessao


class Acesso(BaseModel):
    admin: bool
    """True: a pessoa logada vê o painel de atividade."""


class ContaPainel(BaseModel):
    id: str
    email: str | None = None
    nome: str | None = None
    faculdade: str | None = None
    periodo: str | None = None
    avatar: str | None = None
    criada_em: datetime | None = None
    ultimo_login: datetime | None = None
    ultima_sessao: datetime | None = None
    sessoes: int = 0
    com_colega: int = 0
    """Sessões gravadas com um colega (todas as origens, menos paciente pela IA)."""
    paciente_ia: int = 0
    concluidas: int = 0
    media_geral: int | None = None
    """Média da técnica geral nas sessões com nota."""


class SessaoPainel(BaseModel):
    id: str
    conta_id: str
    criada_em: datetime
    origem_caso: OrigemCaso
    status: StatusSessao
    queixas_confirmadas: list[str]
    descricao_outra: str | None = None
    nota_geral: int | None = None


class DiaPainel(BaseModel):
    dia: date
    sessoes: int


class QueixaPainel(BaseModel):
    queixa: str
    vezes: int


class ResumoPainel(BaseModel):
    contas: int
    ativas_7_dias: int
    """Contas que abriram pelo menos uma sessão nos últimos 7 dias."""
    sessoes: int
    sessoes_7_dias: int
    paciente_ia: int
    concluidas: int


class Painel(BaseModel):
    gerado_em: datetime
    contas_completas: bool
    """False quando a lista de contas não veio do login (sem Supabase): só aparece quem já abriu sessão."""
    resumo: ResumoPainel
    contas: list[ContaPainel]
    recentes: list[SessaoPainel]
    por_dia: list[DiaPainel]
    """Sessões abertas por dia nos últimos 14 dias, do mais antigo para hoje."""
    queixas: list[QueixaPainel]
