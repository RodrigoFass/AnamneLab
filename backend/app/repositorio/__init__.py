"""Persistência das sessões: memória (dev e testes) ou Supabase."""

from app.config import Settings
from app.repositorio.base import Repositorio
from app.repositorio.memoria import RepositorioMemoria

__all__ = ["Repositorio", "RepositorioMemoria", "obter_repositorio"]


def obter_repositorio(settings: Settings) -> Repositorio:
    if settings.banco == "supabase":
        if not settings.supabase_url or not settings.supabase_service_key:
            raise RuntimeError("BANCO=supabase precisa de SUPABASE_URL e SUPABASE_SERVICE_KEY no .env.")
        from app.repositorio.supabase import RepositorioSupabase

        return RepositorioSupabase(settings.supabase_url, settings.supabase_service_key.get_secret_value())
    return RepositorioMemoria()
