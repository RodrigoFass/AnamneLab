"""Correção item a item: o coração do AnamneLab.

O LLM diz, para cada item dos checklists aplicáveis, se foi feito e quais falas provam.
Cada checklist vai num pedido separado: com o geral e o da queixa na mesma lista, o
modelo tende a dar cada fala a um item só, e o da queixa ficava sem nada.

As falas vão numeradas e o LLM cita os números, não o texto. O backend monta o trecho
com as falas citadas, então ele é sempre literal (regra 1), e só aceita o item se uma
delas for do entrevistador: o que o paciente contou sozinho não mostra que o aluno
investigou. Copiar o texto falhava à toa (o modelo corrigia palavras da transcrição)
e não dizia quem falou. O backend também calcula as notas só com os checklists que
contam (regra 3) e registra id, versão e status de cada checklist usado (regra 4).
"""

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import groupby

from app.conteudo import QUEIXA_OUTRA, Conteudo
from app.llm import ClienteLLM, ErroLLM
from app.pipeline.comum import ROTULOS, falas_para_contexto
from app.schemas.conteudo import Checklist, Item, Secao
from app.schemas.llm import CorrecaoLLM, Fala, ItemCorrigido, TrechoCumpreItem
from app.schemas.sessao import (
    Avaliacao,
    ChecklistUsado,
    Contestacao,
    ContestacaoCriar,
    Notas,
)
from app.texto import normalizar

MINIMO_CARACTERES_TRECHO = 4
"""Trecho normalizado mais curto que isso ('sim', 'é') não prova nada."""

SISTEMA = """\
Você é um preceptor que corrige a técnica de anamnese de um estudante de Medicina. \
A conversa é uma simulação entre dois estudantes: o entrevistador faz o médico.

Para cada item do checklist enviado, diga se o entrevistador investigou aquilo na conversa. \
As falas da transcrição vêm numeradas, como [12].

Regras:
- Avalie cada item sozinho, sem pensar nos outros. A mesma fala pode provar vários itens, \
deste checklist ou de outro. Uma pergunta que junta assuntos ("tem falta de ar ou \
batedeira?") vale para cada um deles.
- O entrevistador não precisa usar as palavras do item nem da pergunta de exemplo. Vale \
a pergunta feita com outras palavras, desde que trate do mesmo assunto.
- Procure na conversa inteira, do começo ao fim. A pergunta pode estar em qualquer parte, \
inclusive no meio de uma fala longa ou junto com outras perguntas.
- Um item é feito quando o entrevistador perguntou ou explorou o assunto. Em falas, ponha o \
número da fala do entrevistador que mostra isso e, se ajudar, o da resposta do paciente \
logo depois: [12, 13].
- Em citacao, copie dessas falas só o pedaço curto que mostra o item, como está escrito: a \
pergunta, ou a pergunta e o começo da resposta, com no máximo 25 palavras. Item não feito: \
citacao é null.
- Vale o que o paciente contou na resposta a uma pergunta do entrevistador, mesmo aberta \
("como é essa dor?", "me conte mais"): cite a pergunta e a resposta logo depois. A pergunta \
aberta vale só para o que está nessa resposta.
- Confira a resposta à primeira pergunta sobre o motivo da consulta ("o que te traz aqui?") \
contra todos os itens. Ela costuma trazer vários fatos de uma vez: se o paciente disse \
"estou com diarreia há três dias, umas seis vezes por dia", os itens de duração e de \
frequência foram investigados. Cite a pergunta e essa resposta em cada item que ela cumpre.
- Também é feito o item que a resposta a outra pergunta já esclareceu: o entrevistador \
perguntou se quem comeu junto também passou mal e o paciente disse que comeu sozinho; \
nesse caso, o item sobre outras pessoas com o mesmo quadro foi investigado. Cite a \
pergunta e a resposta.
- O que o paciente contou em outro momento, fora da resposta à pergunta, não basta. Só conta \
se o entrevistador voltou ao assunto, e aí cite essa fala do entrevistador.
- Se nenhuma fala do entrevistador trata do assunto do item, feito é false, falas é [] e citacao é null. \
Não marque por suposição.
- Responda exatamente um registro por item, com o item_id igual ao enviado. Não crie itens.
- A transcrição vem de reconhecimento de voz e pode ter palavras erradas; julgue pelo sentido.
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
- O que o paciente contou sem ser perguntado não cumpre: o trecho precisa mostrar o \
entrevistador perguntando ou explorando o assunto.
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


def itens_aplicaveis(
    checklists: list[Checklist], contar_rascunho: bool, sexo_paciente: str | None = None
) -> list[ItemAplicavel]:
    """Itens na ordem dos checklists. Id repetido entre checklists conta uma vez (fica o primeiro).
    Item só de um sexo sai quando o paciente é do outro; sexo desconhecido mantém todos."""
    vistos: set[str] = set()
    itens: list[ItemAplicavel] = []
    for checklist in checklists:
        for secao in checklist.secoes:
            for item in secao.itens:
                if item.id in vistos:
                    continue
                if item.sexo and sexo_paciente and item.sexo != sexo_paciente:
                    continue
                vistos.add(item.id)
                itens.append(ItemAplicavel(item, secao, checklist, conta_na_nota(checklist, contar_rascunho)))
    return itens


# ---------- conferência dos trechos (regra 1) ----------


_ROTULO_PAPEL = re.compile(r"\b(?:entrevistador|paciente)\s*:", re.IGNORECASE)
"""Rótulo de papel que o LLM vê na transcrição ('Entrevistador:', 'Paciente:')."""


@dataclass(frozen=True)
class TranscricaoNormalizada:
    """A transcrição normalizada, para conferir um trecho escrito (o da contestação)."""

    corrida: str
    """Falas juntas, sem os papéis."""
    do_entrevistador: tuple[tuple[int, int], ...] = ()
    """Início e fim de cada fala do entrevistador em `corrida`."""

    @classmethod
    def de(cls, falas: list[Fala]) -> "TranscricaoNormalizada":
        partes: list[str] = []
        faixas: list[tuple[int, int]] = []
        inicio = 0
        for fala in falas:
            texto = normalizar(fala.texto)
            if not texto:
                continue
            if fala.papel == "entrevistador":
                faixas.append((inicio, inicio + len(texto)))
            partes.append(texto)
            inicio += len(texto) + 1  # o espaço entre as falas
        return cls(corrida=" ".join(partes), do_entrevistador=tuple(faixas))

    def _posicoes(self, trecho: str | None) -> list[tuple[int, int]]:
        """Onde o trecho aparece, em palavras inteiras. Rótulos de papel são tirados antes:
        um trecho que é só 'Entrevistador:' não prova nada."""
        if not trecho:
            return []
        alvo = normalizar(_ROTULO_PAPEL.sub(" ", trecho))
        if len(alvo) < MINIMO_CARACTERES_TRECHO:
            return []
        texto, procura = f" {self.corrida} ", f" {alvo} "
        posicoes = []
        achou = texto.find(procura)
        while achou != -1:
            # O espaço extra no começo de `texto` compensa o de `procura`: achou já é o índice em corrida.
            posicoes.append((achou, achou + len(alvo)))
            achou = texto.find(procura, achou + 1)
        return posicoes

    def tem(self, trecho: str | None) -> bool:
        """O trecho está na transcrição."""
        return bool(self._posicoes(trecho))

    def mostra_entrevistador(self, trecho: str | None) -> bool:
        """O trecho está na transcrição e pega parte de uma fala do entrevistador."""
        return any(
            min(fim, b) - max(inicio, a) >= MINIMO_CARACTERES_TRECHO
            for inicio, fim in self._posicoes(trecho)
            for a, b in self.do_entrevistador
        )


def numerar_falas(falas: list[Fala]) -> str:
    """Transcrição para o prompt da correção, com o número de cada fala, a partir de 1."""
    return "\n".join(f"[{numero}] {ROTULOS[f.papel]}: {f.texto}" for numero, f in enumerate(falas, 1))


def falas_que_provam(numeros: list[int], falas: list[Fala]) -> list[Fala]:
    """As falas que provam o item, entre as que o LLM citou (números a partir de 1).

    Vale a primeira fala citada do entrevistador, mais a fala seguinte se ela também foi
    citada (a resposta). Sem fala do entrevistador entre as citadas, nenhuma vale.
    Número fora da transcrição é ignorado."""
    citadas = sorted({n - 1 for n in numeros if 1 <= n <= len(falas)})
    pergunta = next((i for i in citadas if falas[i].papel == "entrevistador"), None)
    if pergunta is None:
        return []
    usadas = [pergunta, pergunta + 1] if pergunta + 1 in citadas else [pergunta]
    return [falas[i] for i in usadas]


def trecho_do_item(registro: ItemCorrigido, falas: list[Fala]) -> str | None:
    """O trecho mostrado ao aluno, sempre literal (regra 1). A citação curta do LLM vale se
    estiver nas falas que provam o item e pegar a fala do entrevistador; senão, vão as falas
    inteiras. Sem falas que provam, não há trecho e o item é faltou."""
    usadas = falas_que_provam(registro.falas, falas)
    trecho = " ".join(f.texto.strip() for f in usadas)
    if len(normalizar(trecho)) < MINIMO_CARACTERES_TRECHO:
        return None
    citacao = (registro.citacao or "").strip()
    if citacao and TranscricaoNormalizada.de(usadas).mostra_entrevistador(citacao):
        return citacao
    return trecho


def mensagem_feito(texto: str) -> str:
    texto = texto.strip().rstrip(".")
    # Minúscula só na primeira letra, e não em sigla ("HAS", "IAM").
    if len(texto) > 1 and not texto[1].isupper():
        texto = texto[0].lower() + texto[1:]
    return f"Você investigou: {texto}."


# ---------- correção ----------


def montar_avaliacoes(itens: list[ItemAplicavel], resposta: CorrecaoLLM, falas: list[Fala]) -> list[Avaliacao]:
    """Uma avaliação por item. Sem registro ou sem fala do entrevistador citada: faltou."""
    registros = {}
    for registro in resposta.itens:
        registros.setdefault(registro.item_id, registro)

    avaliacoes = []
    for aplicavel in itens:
        item = aplicavel.item
        registro = registros.get(item.id)
        trecho = trecho_do_item(registro, falas) if registro and registro.feito else None
        feito = trecho is not None
        avaliacoes.append(
            Avaliacao(
                item_id=item.id,
                checklist_id=aplicavel.checklist.id,
                secao=aplicavel.secao.titulo,
                texto=item.texto,
                status="feito" if feito else "faltou",
                trecho=trecho,
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


def dividir_em_pedidos(itens: list[ItemAplicavel], limite: int) -> list[list[ItemAplicavel]]:
    """Itens de um checklist em pedidos de até `limite` itens, sem partir uma seção quando ela
    cabe inteira num pedido. Limite 0 (ou menor): tudo num pedido só."""
    if limite <= 0 or len(itens) <= limite:
        return [itens] if itens else []
    pedidos: list[list[ItemAplicavel]] = []
    atual: list[ItemAplicavel] = []
    for _, da_secao in groupby(itens, key=lambda a: a.secao.titulo):
        secao = list(da_secao)
        for inicio in range(0, len(secao), limite):
            pedaco = secao[inicio : inicio + limite]
            if atual and len(atual) + len(pedaco) > limite:
                pedidos.append(atual)
                atual = []
            atual.extend(pedaco)
    if atual:
        pedidos.append(atual)
    return pedidos


def _corrigir_checklist(
    checklist: Checklist, itens: list[ItemAplicavel], falas: list[Fala], llm: ClienteLLM
) -> list[ItemCorrigido]:
    """Um pedido ao LLM com os itens de um checklist. Registro de item que não foi pedido é ignorado."""
    lista = [{"id": a.item.id, "texto": a.item.texto, "pergunta_exemplo": a.item.pergunta_exemplo} for a in itens]
    tipo = "geral, da técnica da entrevista" if checklist.tipo == "geral" else "específico da queixa"
    mensagem = (
        f"Checklist {tipo}: {checklist.nome} ({len(lista)} itens):\n"
        f"{json.dumps(lista, ensure_ascii=False, indent=1)}\n\n"
        f"Transcrição:\n<transcricao>\n{numerar_falas(falas)}\n</transcricao>"
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
    itens_por_pedido: int = 0,
    sexo_paciente: str | None = None,
) -> ResultadoCorrecao:
    """Um pedido ao LLM por checklist, ou mais de um se ele passa de `itens_por_pedido` itens."""
    checklists = checklists_aplicaveis(queixas_confirmadas, conteudo)
    itens = itens_aplicaveis(checklists, contar_rascunho, sexo_paciente)
    registros: list[ItemCorrigido] = []
    for checklist in checklists:
        do_checklist = [a for a in itens if a.checklist.id == checklist.id]
        for pedido in dividir_em_pedidos(do_checklist, itens_por_pedido):
            registros.extend(_corrigir_checklist(checklist, pedido, falas, llm))
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
    """Procedente só se o trecho existe na transcrição, pega uma fala do entrevistador e o LLM
    confirma que ele mostra o item: o item vira feito e a nota é recalculada. Nos outros casos
    (sem trecho, trecho que não existe ou só do paciente, LLM que nega ou falha), fica pendente
    para o professor e a nota não muda.

    `item` é o item como está no conteúdo (texto, pergunta de exemplo, palavras-chave)."""
    indice = next((i for i, a in enumerate(avaliacoes) if a.item_id == pedido.item_id), None)
    if indice is None:
        raise ErroContestacao(404, "Esse item não está na correção desta sessão.")
    atual = avaliacoes[indice]
    if atual.status == "feito":
        raise ErroContestacao(409, "Esse item já está como feito.")

    trecho = pedido.trecho.strip() if pedido.trecho else None
    procedente = bool(
        trecho
        and TranscricaoNormalizada.de(falas).mostra_entrevistador(trecho)
        and trecho_cumpre_item(trecho, atual.texto, item, llm)
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
