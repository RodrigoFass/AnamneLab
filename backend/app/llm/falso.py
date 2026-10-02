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
            "paciente_caso": _paciente_caso,
            "paciente_resposta": _paciente_resposta,
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
    sexo = _sexo(falas)

    for fala in janela:
        texto = normalizar(fala["texto"])
        for queixa in queixas:
            termos = [normalizar(t) for t in [queixa["nome"], *queixa.get("sinonimos", [])] if normalizar(t)]
            if any(termo in texto for termo in termos):
                return {
                    "queixas": [queixa["id"]],
                    "descricao_outra": None,
                    "trecho": fala["texto"],
                    "sexo_paciente": sexo,
                }
    primeira = janela[0]["texto"] if janela else ""
    return {"queixas": ["outra"], "descricao_outra": primeira[:80] or None, "trecho": primeira, "sexo_paciente": sexo}


def _sexo(falas: list[dict[str, str]]) -> str | None:
    """Pelo tratamento que o entrevistador usa: "a senhora" ou "o senhor"."""
    texto = f" {normalizar(' '.join(f['texto'] for f in falas if f['papel'] == 'entrevistador'))} "
    if " senhora " in texto:
        return "feminino"
    if " senhor " in texto:
        return "masculino"
    return None


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
    """Cita a primeira fala do entrevistador com uma palavra-chave do item, pelo número (a partir de 1)."""
    falas = contexto.get("falas", [])
    do_entrevistador = [
        (numero, normalizar(f["texto"])) for numero, f in enumerate(falas, 1) if f["papel"] == "entrevistador"
    ]
    itens = []
    for item in contexto.get("itens", []):
        chaves = [normalizar(p) for p in item.get("palavras_chave", []) if normalizar(p)]
        numero = next((n for n, texto in do_entrevistador if any(chave in texto for chave in chaves)), None)
        itens.append(
            {"item_id": item["id"], "feito": numero is not None, "falas": [numero] if numero else [], "citacao": None}
        )
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


def _paciente_caso(contexto: dict[str, Any]) -> dict[str, Any]:
    """Ficha fixa a partir do cartão: os detalhes dele viram a história da doença."""
    cartao: dict[str, Any] = contexto.get("cartao", {})
    mulher = cartao.get("sexo") == "feminino"
    return {
        "nome": "Maria Souza" if mulher else "José Lima",
        "idade": cartao.get("idade", 40),
        "sexo": "feminino" if mulher else "masculino",
        "profissao": "professora" if mulher else "motorista",
        "queixa_nas_palavras_dele": cartao.get("resumo", "Não estou me sentindo bem."),
        "historia_da_doenca": [*cartao.get("detalhes", []), "Nunca senti isso antes."],
        "antecedentes": ["Tenho pressão alta há uns cinco anos."],
        "medicacoes": ["Tomo losartana de manhã."],
        "alergias": ["Não tenho alergia a remédio."],
        "habitos": ["Não bebo. Caminho no fim de semana."],
        "familia": ["Meu pai teve infarto aos 60 anos."],
        "vida_social": ["Moro com a família e trabalho de dia."],
        "jeito_de_falar": "Tranquilo, responde direto.",
    }


_TEMAS_PACIENTE: list[tuple[tuple[str, ...], str]] = [
    (("nome", "chama"), "nome"),
    (("idade", "anos voce tem", "quantos anos"), "idade"),
    (("trabalh", "profiss", "faz da vida"), "profissao"),
    (("remedio", "medica"), "medicacoes"),
    (("alergi",), "alergias"),
    (("fuma", "bebe", "alcool", "atividade", "exercicio"), "habitos"),
    (("famil", "pai", "mae", "irmao"), "familia"),
    (("doenca", "problema de saude", "pressao", "diabetes", "cirurgia", "internad"), "antecedentes"),
    (("mora", "casad", "filhos"), "vida_social"),
    (("traz", "motivo", "aconteceu", "ajudar", "sentindo"), "queixa"),
]


def _paciente_resposta(contexto: dict[str, Any]) -> dict[str, Any]:
    """Responde pela primeira palavra-chave que casar; o resto vira um fato da história."""
    caso: dict[str, Any] = contexto.get("caso", {})
    pergunta = normalizar(contexto.get("pergunta", ""))
    for termos, tema in _TEMAS_PACIENTE:
        if any(t in pergunta for t in termos):
            if tema == "nome":
                return {"resposta": f"Meu nome é {caso.get('nome', '')}."}
            if tema == "idade":
                return {"resposta": f"Tenho {caso.get('idade')} anos."}
            if tema == "profissao":
                return {"resposta": f"Trabalho como {caso.get('profissao', '')}."}
            if tema == "queixa":
                return {"resposta": caso.get("queixa_nas_palavras_dele", "")}
            return {"resposta": " ".join(caso.get(tema, [])) or "Não que eu saiba."}
    historia: list[str] = caso.get("historia_da_doenca", [])
    indice = sum(map(ord, pergunta)) % len(historia) if historia else 0
    return {"resposta": historia[indice] if historia else "Não sei dizer."}
