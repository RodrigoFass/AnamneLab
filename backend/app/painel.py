"""Painel de atividade: quem tem conta e o que cada um anda fazendo no app.

Só entra quem tem o e-mail em ADMIN_EMAILS (com AUTH=dev, o aluno de desenvolvimento, para
ver o painel no modo de demonstração). Mostra contagens, datas, queixas e notas; nunca
transcrição, ficha do caso ou correção de ninguém.
"""

import logging
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import ALUNO_DEV_ID, Usuario, e_admin, usuario_atual
from app.config import Settings
from app.schemas.painel import (
    Acesso,
    ContaPainel,
    DiaPainel,
    Painel,
    QueixaPainel,
    ResumoPainel,
    SessaoPainel,
)
from app.schemas.sessao import Sessao
from app.servicos import Servicos

logger = logging.getLogger(__name__)

RECENTES = 40
DIAS_GRAFICO = 14
MENSAGEM_SEM_ACESSO = "Este painel é só para quem cuida do AnamneLab."
MENSAGEM_CONTAS_FORA = "Não deu para buscar as contas agora. Tente de novo em alguns minutos."

rotas_painel = APIRouter(prefix="/api")


def _servicos(request: Request) -> Servicos:
    return request.app.state.servicos


ServicosDep = Annotated[Servicos, Depends(_servicos)]
UsuarioDep = Annotated[Usuario, Depends(usuario_atual)]


def _data(valor: Any) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None


def _texto(valor: Any) -> str | None:
    return str(valor).strip() or None if valor else None


async def contas_do_supabase(settings: Settings) -> list[ContaPainel]:
    """Todas as contas do Supabase Auth, com o perfil que o app guarda nos metadados."""
    if not settings.supabase_url or not settings.supabase_service_key:
        raise HTTPException(503, MENSAGEM_CONTAS_FORA)
    chave = settings.supabase_service_key.get_secret_value()
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users"
    cabecalhos = {"Authorization": f"Bearer {chave}", "apikey": chave}
    usuarios: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=15) as cliente:
            for pagina in range(1, 21):
                resposta = await cliente.get(url, headers=cabecalhos, params={"page": pagina, "per_page": 500})
                if resposta.status_code != 200:
                    logger.warning("Supabase Auth respondeu %s ao listar contas", resposta.status_code)
                    raise HTTPException(503, MENSAGEM_CONTAS_FORA)
                lote = resposta.json().get("users") or []
                usuarios.extend(lote)
                if len(lote) < 500:
                    break
    except httpx.HTTPError:
        logger.warning("Supabase Auth fora do ar ao listar contas")
        raise HTTPException(503, MENSAGEM_CONTAS_FORA) from None

    contas = []
    for u in usuarios:
        perfil = (u.get("user_metadata") or {}).get("perfil") or {}
        contas.append(
            ContaPainel(
                id=str(u.get("id")),
                email=_texto(u.get("email")),
                nome=_texto(perfil.get("nome")),
                faculdade=_texto(perfil.get("faculdade")),
                periodo=_texto(perfil.get("periodo")),
                avatar=_texto(perfil.get("avatar")),
                criada_em=_data(u.get("created_at")),
                ultimo_login=_data(u.get("last_sign_in_at")),
            )
        )
    return contas


def montar_painel(contas: list[ContaPainel], sessoes: list[Sessao], contas_completas: bool, agora: datetime) -> Painel:
    """Junta contas e sessões. Quem abriu sessão mas não está na lista de contas entra só com o id."""
    por_id = {c.id: c for c in contas}
    notas: dict[str, list[int]] = {}
    for s in sessoes:
        conta = por_id.get(s.dono_id)
        if conta is None:
            conta = por_id[s.dono_id] = ContaPainel(id=s.dono_id)
        conta.sessoes += 1
        if s.origem_caso == "paciente_ia":
            conta.paciente_ia += 1
        else:
            conta.com_colega += 1
        if s.status == "concluida":
            conta.concluidas += 1
        if conta.ultima_sessao is None or s.criada_em > conta.ultima_sessao:
            conta.ultima_sessao = s.criada_em
        if s.notas and s.notas.geral is not None:
            notas.setdefault(s.dono_id, []).append(s.notas.geral)
    for conta_id, lista in notas.items():
        por_id[conta_id].media_geral = round(sum(lista) / len(lista))

    def recencia(c: ContaPainel) -> datetime:
        datas = [d for d in (c.ultima_sessao, c.ultimo_login, c.criada_em) if d]
        return max(datas) if datas else datetime.min.replace(tzinfo=UTC)

    todas = sorted(por_id.values(), key=recencia, reverse=True)
    semana = agora - timedelta(days=7)
    hoje = agora.date()
    inicio = hoje - timedelta(days=DIAS_GRAFICO - 1)
    dias = Counter(s.criada_em.astimezone(agora.tzinfo).date() for s in sessoes)
    queixas = Counter(q for s in sessoes for q in s.queixas_confirmadas)

    return Painel(
        gerado_em=agora,
        contas_completas=contas_completas,
        resumo=ResumoPainel(
            contas=len(todas),
            ativas_7_dias=len({s.dono_id for s in sessoes if s.criada_em >= semana}),
            sessoes=len(sessoes),
            sessoes_7_dias=sum(1 for s in sessoes if s.criada_em >= semana),
            paciente_ia=sum(1 for s in sessoes if s.origem_caso == "paciente_ia"),
            concluidas=sum(1 for s in sessoes if s.status == "concluida"),
        ),
        contas=todas,
        recentes=[
            SessaoPainel(
                id=s.id,
                conta_id=s.dono_id,
                criada_em=s.criada_em,
                origem_caso=s.origem_caso,
                status=s.status,
                queixas_confirmadas=s.queixas_confirmadas,
                descricao_outra=s.descricao_outra,
                nota_geral=s.notas.geral if s.notas else None,
            )
            for s in sessoes[:RECENTES]
        ],
        por_dia=[
            DiaPainel(dia=inicio + timedelta(days=i), sessoes=dias.get(inicio + timedelta(days=i), 0))
            for i in range(DIAS_GRAFICO)
        ],
        queixas=[QueixaPainel(queixa=q, vezes=n) for q, n in queixas.most_common(8)],
    )


@rotas_painel.get("/eu/acesso", response_model=Acesso)
def acesso(servicos: ServicosDep, usuario: UsuarioDep) -> Acesso:
    return Acesso(admin=e_admin(servicos.settings, usuario))


@rotas_painel.get("/painel", response_model=Painel)
async def painel(servicos: ServicosDep, usuario: UsuarioDep) -> Painel:
    settings = servicos.settings
    if not e_admin(settings, usuario):
        raise HTTPException(403, MENSAGEM_SEM_ACESSO)
    if settings.auth == "supabase":
        contas, completas = await contas_do_supabase(settings), True
    else:
        contas = [ContaPainel(id=ALUNO_DEV_ID, nome="Aluno de demonstração")]
        completas = False
    sessoes = servicos.repositorio.listar_todas_sessoes()
    return montar_painel(contas, sessoes, completas, datetime.now(UTC))
