"""Provedor falso: determinístico, sem rede, para desenvolvimento e testes.

Responde por `tarefa` usando o `contexto` que o pipeline manda junto. Devolve JSON
no mesmo formato do provedor real, então passa pela mesma validação.
"""

import re
from typing import Any

from pydantic import BaseModel

from app.llm.base import ClienteLLM
from app.texto import normalizar

NAO_ABORDADO = "Não abordado."

_MARCADOR = re.compile(r"(Médico|Medico|Entrevistador|Estudante|Paciente)\s*:", re.IGNORECASE)
_FRASE = re.compile(r"[^.?!]+[.?!]?")

FALAS_PARA_QUEIXA = 3
"""Quantas falas do paciente o falso olha para achar a queixa principal."""

# Ordem importa: a primeira seção cujo termo aparece na pergunta leva a resposta.
_SECOES_ANAMNESE: list[tuple[str, tuple[str, ...]]] = [
    ("queixa_principal", ("traz", "trouxe", "motivo", "queixa", "ajudar", "o que aconteceu", "está sentindo")),
    ("antecedentes_familiares", ("família", "familia", "seu pai", "sua mãe", "seus pais", "irmão", "irmã")),
    (
        "habitos_de_vida",
        ("fuma", "cigarro", "álcool", "bebe", "bebida", "exercício", "atividade física", "alimentação", "droga"),
    ),
    ("condicoes_socioeconomicas", ("casa", "moradia", "saneamento", "renda", "mora com", "quem mora")),
    ("identificacao", ("seu nome", "idade", "quantos anos", "profissão", "trabalha", "estado civil", "onde mora")),
    (
        "interrogatorio_sintomatologico",
        ("febre", "tosse", "emagre", "peso", "urina", "intestino", "sono", "apetite", "inchaço"),
    ),
    (
        "antecedentes_pessoais",
        (
            "doença",
            "pressão",
            "diabetes",
            "remédio",
            "medicação",
            "medicamento",
            "cirurgia",
            "internad",
            "alergia",
            "colesterol",
        ),
    ),
    ("hda", ("",)),  # qualquer outra pergunta entra na história da doença atual
]


class ClienteFalso(ClienteLLM):
    nome = "falso"

    def _gerar_json(
        self,
        *,
        tarefa: str,
        sistema: str,
        mensagem: str,
        saida: type[BaseModel],
        contexto: dict[str, Any] | None,
    ) -> str:
        contexto = contexto or {}
        respostas = {
            "rotular": _rotular,
            "queixa": _queixa,
            "anamnese": _anamnese,
            "corrigir": _corrigir,
            "sugestoes": _sugestoes,
            "verificar_contestacao": _verificar_contestacao,
        }
        if tarefa not in respostas:
            raise ValueError(f"tarefa desconhecida para o provedor falso: {tarefa}")
        return saida.model_validate(respostas[tarefa](contexto)).model_dump_json()


def _rotular(contexto: dict[str, Any]) -> dict[str, Any]:
    texto: str = contexto.get("texto", "")
    falas: list[dict[str, str]] = []
    partes = _MARCADOR.split(texto)
    if len(partes) > 1:
        # partes = [antes, marcador, fala, marcador, fala, ...]
        for marcador, fala in zip(partes[1::2], partes[2::2], strict=True):
            fala = " ".join(fala.split())
            if fala:
                papel = "paciente" if marcador.lower() == "paciente" else "entrevistador"
                falas.append({"papel": papel, "texto": fala})
        return {"falas": falas}
    frases = [f.strip() for f in _FRASE.findall(texto) if f.strip()]
    for indice, frase in enumerate(frases):
        falas.append({"papel": "entrevistador" if indice % 2 == 0 else "paciente", "texto": frase})
    return {"falas": falas}


def _queixa(contexto: dict[str, Any]) -> dict[str, Any]:
    """A queixa principal aparece logo que o paciente conta o motivo da consulta.

    Olha só as primeiras falas do paciente a partir da resposta à pergunta sobre o motivo
    (ou do começo, se essa pergunta não aparece) e devolve só a primeira queixa que casar.
    Sintoma que surge depois, no interrogatório, não vira queixa principal.
    """
    falas: list[dict[str, str]] = contexto.get("falas", [])
    queixas: list[dict[str, Any]] = contexto.get("queixas", [])
    janela = _falas_do_motivo(falas)[:FALAS_PARA_QUEIXA]

    for fala in janela:
        texto = normalizar(fala["texto"])
        for queixa in queixas:
            termos = [normalizar(t) for t in [queixa["nome"], *queixa.get("sinonimos", [])] if normalizar(t)]
            if any(termo in texto for termo in termos):
                return {"queixas": [queixa["id"]], "descricao_outra": None, "trecho": fala["texto"]}
    primeira = janela[0]["texto"] if janela else ""
    return {"queixas": ["outra"], "descricao_outra": primeira[:80] or None, "trecho": primeira}


def _falas_do_motivo(falas: list[dict[str, str]]) -> list[dict[str, str]]:
    """Falas do paciente a partir da resposta à pergunta sobre o motivo da consulta."""
    termos_motivo = dict(_SECOES_ANAMNESE)["queixa_principal"]
    inicio = 0
    for indice, fala in enumerate(falas):
        if fala["papel"] == "entrevistador" and any(t in fala["texto"].casefold() for t in termos_motivo):
            inicio = indice + 1
            break
    do_paciente = [f for f in falas[inicio:] if f["papel"] == "paciente"]
    return do_paciente or [f for f in falas if f["papel"] == "paciente"] or falas


def _anamnese(contexto: dict[str, Any]) -> dict[str, Any]:
    falas: list[dict[str, str]] = contexto.get("falas", [])
    campos: dict[str, list[str]] = {nome: [] for nome, _ in _SECOES_ANAMNESE}
    ultima_pergunta = ""
    for fala in falas:
        if fala["papel"] == "entrevistador":
            ultima_pergunta = fala["texto"].casefold()
            continue
        for nome, termos in _SECOES_ANAMNESE:
            if nome == "queixa_principal" and campos[nome]:
                continue  # a queixa principal é só a primeira resposta
            if any(termo in ultima_pergunta for termo in termos):
                campos[nome].append(fala["texto"])
                break
    return {nome: " ".join(textos) or NAO_ABORDADO for nome, textos in campos.items()}


def _corrigir(contexto: dict[str, Any]) -> dict[str, Any]:
    falas = [f for f in contexto.get("falas", []) if f["papel"] == "entrevistador"]
    normalizadas = [(f["texto"], normalizar(f["texto"])) for f in falas]
    itens = []
    for item in contexto.get("itens", []):
        chaves = [normalizar(p) for p in item.get("palavras_chave", []) if normalizar(p)]
        trecho = next(
            (original for original, texto in normalizadas if any(chave in texto for chave in chaves)),
            None,
        )
        itens.append({"item_id": item["id"], "feito": trecho is not None, "trecho": trecho})
    return {"itens": itens}


def _sugestoes(contexto: dict[str, Any]) -> dict[str, Any]:
    """Perguntas só quando falta checklist para a queixa (mesma regra do pipeline)."""
    faltantes = contexto.get("itens_faltantes", [])
    pedir_perguntas = bool(contexto.get("pedir_perguntas"))
    return {
        "hipoteses": [
            {
                "nome": "Exemplo de hipótese (modo de desenvolvimento, sem IA)",
                "a_favor": ["Exemplo: dado da conversa que apoiaria a hipótese."],
                "contra": ["Exemplo: dado que falta ou que pesa contra."],
            }
        ],
        "perguntas_sugeridas": [item["texto"] for item in faltantes] if pedir_perguntas else [],
    }


def _verificar_contestacao(contexto: dict[str, Any]) -> dict[str, Any]:
    """Cumpre se alguma palavra-chave do item aparece no trecho apontado."""
    trecho = normalizar(contexto.get("trecho") or "")
    item = contexto.get("item") or {}
    chaves = [normalizar(p) for p in item.get("palavras_chave", []) if normalizar(p)]
    return {"cumpre": any(chave in trecho for chave in chaves)}
