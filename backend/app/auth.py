"""Quem está chamando a API.

AUTH=dev: um aluno fixo de desenvolvimento, sem login.
AUTH=supabase: confere o Bearer token no Supabase Auth e usa o id do usuário.
"""

import logging
from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings

logger = logging.getLogger(__name__)

ALUNO_DEV_ID = "00000000-0000-4000-8000-000000000001"

MENSAGEM_SEM_LOGIN = "Entre de novo para continuar."
MENSAGEM_AUTH_FORA = "Não deu para conferir seu login agora. Tente de novo em alguns minutos."

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Usuario:
    id: str
    email: str | None = None


def _settings(request: Request) -> Settings:
    return request.app.state.servicos.settings


async def conferir_token_supabase(settings: Settings, token: str) -> Usuario:
    if not settings.supabase_url or not settings.supabase_service_key:
        logger.error("AUTH=supabase sem SUPABASE_URL ou SUPABASE_SERVICE_KEY")
        raise HTTPException(503, MENSAGEM_AUTH_FORA)
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/user"
    cabecalhos = {
        "Authorization": f"Bearer {token}",
        "apikey": settings.supabase_service_key.get_secret_value(),
    }
    try:
        async with httpx.AsyncClient(timeout=10) as cliente:
            resposta = await cliente.get(url, headers=cabecalhos)
    except httpx.HTTPError:
        logger.warning("Supabase Auth fora do ar")
        raise HTTPException(503, MENSAGEM_AUTH_FORA) from None
    if resposta.status_code != 200:
        raise HTTPException(401, MENSAGEM_SEM_LOGIN, headers={"WWW-Authenticate": "Bearer"})
    usuario_id = resposta.json().get("id")
    if not usuario_id:
        raise HTTPException(401, MENSAGEM_SEM_LOGIN, headers={"WWW-Authenticate": "Bearer"})
    email = resposta.json().get("email")
    return Usuario(id=str(usuario_id), email=str(email) if email else None)


def e_admin(settings: Settings, usuario: Usuario) -> bool:
    """Quem vê o painel de atividade: e-mail em ADMIN_EMAILS ou, sem login, o aluno de desenvolvimento."""
    if settings.auth == "dev":
        return usuario.id == ALUNO_DEV_ID
    return bool(usuario.email) and usuario.email.lower() in settings.lista_admin_emails


async def usuario_atual(
    request: Request,
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Usuario:
    settings = _settings(request)
    if settings.auth == "dev":
        return Usuario(id=ALUNO_DEV_ID)
    if credenciais is None or not credenciais.credentials:
        raise HTTPException(401, MENSAGEM_SEM_LOGIN, headers={"WWW-Authenticate": "Bearer"})
    return await conferir_token_supabase(settings, credenciais.credentials)
