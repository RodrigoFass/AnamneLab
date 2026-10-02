"""Correção item a item: o coração do AnamneLab.

O LLM diz, para cada item dos checklists aplicáveis, se foi feito e qual fala prova.
Cada checklist vai num pedido separado: com o geral e o da queixa na mesma lista, o
modelo tende a dar cada fala a um item só, e o da queixa ficava sem nada. O backend
não confia: confere cada trecho na transcrição (regra 1), calcula as notas só com os
checklists que contam (regra 3) e registra id, versão e status de cada checklist
usado (regra 4).
"""

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from app.conteudo import QUEIXA_OUTRA, Conteudo
from app.llm import ClienteLLM, ErroLLM
from app.pipeline.comum import falas_para_contexto, formatar_falas
from app.schemas.conteudo import Checklist, Item, Secao
from app.schemas.llm import CorrecaoLLM, Fala, ItemCorrigido, TrechoCumpreItem
from app.schemas.sessao import (
    Avaliacao,
    ChecklistUsado,
    Contestacao,
    ContestacaoCriar,
    Notas,
)
from app.texto import contem, normalizar

MINIMO_CARACTERES_TRECHO = 4
"""Trecho normalizado mais curto que isso ('sim', 'é') não prova nada."""

SISTEMA = """\
Você é um preceptor que corrige a técnica de anamnese de um estudante de Medicina. \
A conversa é uma simulação entre dois estudantes: o entrevistador faz o médico.

Para cada item do checklist enviado, diga se o entrevistador investigou aquilo na conversa.

Regras:
- Avalie cada item sozinho, sem pensar nos outros. A mesma fala pode provar vários itens, \
deste checklist ou de outro. Uma pergunta que junta assuntos ("tem falta de ar ou \
batedeira?") vale para cada um deles.
- O entrevistador não precisa usar as palavras do item nem da pergunta de exemplo. Vale \
a pergunta feita com outras palavras, desde que trate do mesmo assunto.
- Um item só é feito se houver na transcrição uma fala que mostre isso. Em trecho, copie \
essa fala literalmente, como está na transcrição, sem corrigir, resumir ou juntar pedaços \
distantes. Pode ser a pergunta do entrevistador ou a pergunta seguida da resposta.
- Avalie o que o entrevistador perguntou ou explorou. Informação que o paciente deu sem \
ser perguntado só conta se o entrevistador voltou ao assunto.
- Se nenhuma fala trata do assunto do item, feito é false e trecho é null. Não marque \
por suposição.
- Responda exatamente um registro por item, com o item_id igual ao enviado. Não crie itens.
- A transcrição vem de reconhecimento de voz e pode ter palavras erradas; julgue pelo \
sentido, mas copie o trecho como está escrito.
- Não avalie diagnóstico nem conduta; só a técnica da entrevista.
"""


SISTEMA_CONTESTACAO = """\
Você é um preceptor que confere a contestação de um estudante de Medicina numa simulação \
de anamnese entre dois estudantes. O entrevistador faz o médico.

O estudante diz que fez um item do checklist e aponta um trecho da conversa. Diga se esse \
trecho mostra que o entrevistador investigou o item.

Regras:
- Avalie só a técnica da entrevista, não o diagnóstico nem a conduta.
- O trecho precisa tratar do item. Uma fala sobre outro assunto não cumpre o item.
- Na dúvida, cumpre é false: a contestação vai para o professor.
"""


@dataclass(frozen=True)
class ItemAplicavel:
    item: Item
    secao: Secao
    checklist: Checklist
    conta_na_nota: bool


@dataclass(frozen=True)
class ResultadoCorrecao:
    avaliacoes: list[Avaliacao]
    notas: Notas
    checklists_usados: list[ChecklistUsado]


@dataclass(frozen=True)
class ResultadoContestacao:
    avaliacoes: list[Avaliacao]
    notas: Notas | None
    contestacao: Contestacao


class ErroContestacao(Exception):
    def __init__(self, codigo: int, mensagem: str) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem


# ---------- checklists e itens ----------


def checklists_aplicaveis(queixas_confirmadas: list[str], conteudo: Conteudo) -> list[Checklist]:
    """Geral + os checklists das queixas confirmadas que têm checklist. 'outra' só usa o geral."""
    checklists = [conteudo.checklist_geral]
    for queixa_id in queixas_confirmadas:
        if queixa_id == QUEIXA_OUTRA:
            continue
        checklist = conteudo.checklist_da_queixa(queixa_id)
        if checklist is not None and checklist.id not in {c.id for c in checklists}:
            checklists.append(checklist)
    return checklists


def conta_na_nota(checklist: Checklist, contar_rascunho: bool) -> bool:
    return checklist.aprovado or contar_rascunho


def registrar_checklists(checklists: list[Checklist], contar_rascunho: bool) -> list[ChecklistUsado]:
    return [
        ChecklistUsado(id=c.id, versao=c.versao, status=c.status, conta_na_nota=conta_na_nota(c, contar_rascunho))
        for c in checklists
    ]


def itens_aplicaveis(checklists: list[Checklist], contar_rascunho: bool) -> list[ItemAplicavel]:
    """Itens na ordem dos checklists. Id repetido entre checklists conta uma vez (fica o primeiro)."""
    vistos: set[str] = set()
    itens: list[ItemAplicavel] = []
    for checklist in checklists:
        for secao in checklist.secoes:
            for item in secao.itens:
                if item.id in vistos:
                    continue
                vistos.add(item.id)
                itens.append(ItemAplicavel(item, secao, checklist, conta_na_nota(checklist, contar_rascunho)))
    return itens


# ---------- conferência dos trechos (regra 1) ----------


_ROTULO_PAPEL = re.compile(r"\b(?:entrevistador|paciente)\s*:", re.IGNORECASE)
"""Rótulo de papel que o LLM vê na transcrição ('Entrevistador:', 'Paciente:')."""


@dataclass(frozen=True)
class TranscricaoNormalizada:
    corrida: str
    """Falas juntas, sem os papéis."""

    @classmethod
    def de(cls, falas: list[Fala]) -> "TranscricaoNormalizada":
        return cls(corrida=normalizar(" ".join(f.texto for f in falas)))

    def tem(self, trecho: str | None) -> bool:
        """O trecho está na transcrição. Rótulos de papel são tirados antes de conferir:
        um trecho que é só 'Entrevistador:' não prova nada."""
        if not trecho:
            return False
        alvo = normalizar(_ROTULO_PAPEL.sub(" ", trecho))
        if len(alvo) < MINIMO_CARACTERES_TRECHO:
            return False
        return contem(alvo, self.corrida)


def mensagem_feito(texto: str) -> str:
    texto = texto.strip().rstrip(".")
    # Minúscula só na primeira letra, e não em sigla ("HAS", "IAM").
    if len(texto) > 1 and not texto[1].isupper():
        texto = texto[0].lower() + texto[1:]
    return f"Você investigou: {texto}."


# ---------- correção ----------


def montar_avaliacoes(itens: list[ItemAplicavel], resposta: CorrecaoLLM, falas: list[Fala]) -> list[Avaliacao]:
    """Uma avaliação por item. Sem registro, sem trecho ou trecho inexistente: faltou."""
    transcricao = TranscricaoNormalizada.de(falas)
    registros = {}
    for registro in resposta.itens:
        registros.setdefault(registro.item_id, registro)

    avaliacoes = []
    for aplicavel in itens:
        item = aplicavel.item
        registro = registros.get(item.id)
        feito = bool(registro and registro.feito and transcricao.tem(registro.trecho))
        avaliacoes.append(
            Avaliacao(
                item_id=item.id,
                checklist_id=aplicavel.checklist.id,
                secao=aplicavel.secao.titulo,
                texto=item.texto,
                status="feito" if feito else "faltou",
                trecho=registro.trecho.strip() if feito and registro and registro.trecho else None,
                mensagem=mensagem_feito(item.texto) if feito else item.faltou,
                peso=item.peso,
                conta_na_nota=aplicavel.conta_na_nota,
            )
        )
    return avaliacoes


def _nota(avaliacoes: list[Avaliacao]) -> int | None:
    total = sum(a.peso for a in avaliacoes)
    if total == 0:
        return None
    feitos = sum(a.peso for a in avaliacoes if a.status == "feito")
    # Arredondamento comercial (0,5 sobe), em inteiros para não depender de float.
    return (200 * feitos + total) // (2 * total)


def calcular_notas(
    avaliacoes: list[Avaliacao], checklists_usados: list[ChecklistUsado], tipos: dict[str, str]
) -> Notas:
    """Nota = soma dos pesos feitos / soma dos pesos, de 0 a 100, só com o que conta na nota."""
    contam = [a for a in avaliacoes if a.conta_na_nota]
    geral = [a for a in contam if tipos.get(a.checklist_id) == "geral"]
    queixa = [a for a in contam if tipos.get(a.checklist_id) == "queixa"]
    provisoria = any(c.conta_na_nota and c.status == "rascunho" for c in checklists_usados)
    return Notas(geral=_nota(geral), queixa=_nota(queixa), provisoria=provisoria)


def _corrigir_checklist(
    checklist: Checklist, itens: list[ItemAplicavel], falas: list[Fala], llm: ClienteLLM
) -> list[ItemCorrigido]:
    """Um pedido ao LLM com os itens de um checklist. Registro de item que não foi pedido é ignorado."""
    lista = [{"id": a.item.id, "texto": a.item.texto, "pergunta_exemplo": a.item.pergunta_exemplo} for a in itens]
    tipo = "geral, da técnica da entrevista" if checklist.tipo == "geral" else "específico da queixa"
    mensagem = (
        f"Checklist {tipo}: {checklist.nome} ({len(lista)} itens):\n"
        f"{json.dumps(lista, ensure_ascii=False, indent=1)}\n\n"
        f"Transcrição:\n<transcricao>\n{formatar_falas(falas)}\n</transcricao>"
    )
    resposta = llm.gerar(
        tarefa="corrigir",
        sistema=SISTEMA,
        mensagem=mensagem,
        saida=CorrecaoLLM,
        contexto={
            "falas": falas_para_contexto(falas),
            "itens": [{"id": a.item.id, "texto": a.item.texto, "palavras_chave": a.item.palavras_chave} for a in itens],
        },
    )
    pedidos = {a.item.id for a in itens}
    return [registro for registro in resposta.itens if registro.item_id in pedidos]


def corrigir(
    falas: list[Fala],
    queixas_confirmadas: list[str],
    conteudo: Conteudo,
    llm: ClienteLLM,
    *,
    contar_rascunho: bool,
) -> ResultadoCorrecao:
    checklists = checklists_aplicaveis(queixas_confirmadas, conteudo)
    itens = itens_aplicaveis(checklists, contar_rascunho)
    registros: list[ItemCorrigido] = []
    for checklist in checklists:
        do_checklist = [a for a in itens if a.checklist.id == checklist.id]
        if do_checklist:
            registros.extend(_corrigir_checklist(checklist, do_checklist, falas, llm))
    avaliacoes = montar_avaliacoes(itens, CorrecaoLLM(itens=registros), falas)
    usados = registrar_checklists(checklists, contar_rascunho)
    tipos = {c.id: c.tipo for c in checklists}
    return ResultadoCorrecao(
        avaliacoes=avaliacoes, notas=calcular_notas(avaliacoes, usados, tipos), checklists_usados=usados
    )


# ---------- contestação ----------


def item_do_checklist(conteudo: Conteudo, checklist_id: str, item_id: str) -> Item | None:
    """O item como está no conteúdo, para levar o texto e a pergunta de exemplo ao LLM."""
    checklist = conteudo.checklists.get(checklist_id)
    if checklist is None:
        return None
    return next((i for i in checklist.itens if i.id == item_id), None)


def trecho_cumpre_item(trecho: str, texto_item: str, item: Item | None, llm: ClienteLLM) -> bool:
    """O LLM confere se o trecho mostra o item. Falha do LLM conta como não (vai ao professor)."""
    pergunta = item.pergunta_exemplo if item and item.pergunta_exemplo else "não há"
    mensagem = (
        f"Item do checklist: {texto_item}\n"
        f"Pergunta de exemplo: {pergunta}\n\n"
        f"Trecho apontado pelo estudante:\n<trecho>\n{trecho}\n</trecho>"
    )
    try:
        resposta = llm.gerar(
            tarefa="verificar_contestacao",
            sistema=SISTEMA_CONTESTACAO,
            mensagem=mensagem,
            saida=TrechoCumpreItem,
            contexto={
                "item": {"texto": texto_item, "palavras_chave": item.palavras_chave if item else []},
                "trecho": trecho,
            },
        )
    except ErroLLM:
        return False
    return resposta.cumpre


def contestar(
    avaliacoes: list[Avaliacao],
    falas: list[Fala],
    pedido: ContestacaoCriar,
    checklists_usados: list[ChecklistUsado],
    tipos: dict[str, str],
    notas_atuais: Notas | None,
    *,
    item: Item | None,
    llm: ClienteLLM,
) -> ResultadoContestacao:
    """Procedente só se o trecho existe na transcrição e o LLM confirma que ele mostra o item:
    o item vira feito e a nota é recalculada. Nos outros casos (sem trecho, trecho que não
    existe, LLM que nega ou falha), fica pendente para o professor e a nota não muda.

    `item` é o item como está no conteúdo (texto, pergunta de exemplo, palavras-chave)."""
    indice = next((i for i, a in enumerate(avaliacoes) if a.item_id == pedido.item_id), None)
    if indice is None:
        raise ErroContestacao(404, "Esse item não está na correção desta sessão.")
    atual = avaliacoes[indice]
    if atual.status == "feito":
        raise ErroContestacao(409, "Esse item já está como feito.")

    trecho = pedido.trecho.strip() if pedido.trecho else None
    procedente = bool(
        trecho and TranscricaoNormalizada.de(falas).tem(trecho) and trecho_cumpre_item(trecho, atual.texto, item, llm)
    )
    contestacao = Contestacao(
        item_id=pedido.item_id,
        motivo=pedido.motivo.strip(),
        trecho=trecho,
        resultado="procedente" if procedente else "pendente_professor",
        criada_em=datetime.now(UTC),
    )
    novas = list(avaliacoes)
    if procedente:
        novas[indice] = atual.model_copy(
            update={
                "status": "feito",
                "trecho": contestacao.trecho,
                "mensagem": mensagem_feito(atual.texto),
                "contestacao": contestacao,
            }
        )
        notas = calcular_notas(novas, checklists_usados, tipos)
    else:
        novas[indice] = atual.model_copy(update={"contestacao": contestacao})
        notas = notas_atuais
    return ResultadoContestacao(avaliacoes=novas, notas=notas, contestacao=contestacao)
