"""Normalização de texto usada para conferir trechos e agrupar queixas."""

import re
import unicodedata

_ESPACOS = re.compile(r"\s+")


def normalizar(texto: str) -> str:
    """Casefold, sem pontuação nem símbolos, espaços colapsados. Mantém os acentos."""
    texto = unicodedata.normalize("NFC", texto).casefold()
    sem_pontuacao = "".join(" " if unicodedata.category(c)[0] in ("P", "S") else c for c in texto)
    return _ESPACOS.sub(" ", sem_pontuacao).strip()


def contem(trecho_normalizado: str, texto_normalizado: str) -> bool:
    """O trecho aparece no texto como palavras inteiras (ambos já normalizados)."""
    if not trecho_normalizado:
        return False
    return f" {trecho_normalizado} " in f" {texto_normalizado} "
