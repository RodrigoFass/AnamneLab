"""Hipóteses sugeridas para estudo e perguntas que ajudariam.

Roda só depois que o aluno escreveu as hipóteses dele. Nunca afirma diagnóstico
(regra 6): a interface mostra tudo como "sugestão, não gabarito". Fica fora da nota.

As perguntas sugeridas são a terceira camada da correção: só existem quando alguma
queixa confirmada é "outra" ou não tem checklist. Com checklist para todas as queixas,
o backend devolve a lista vazia, diga o LLM o que disser.
"""

import json

from app.conteudo import QUEIXA_OUTRA, Conteudo
from app.llm import ClienteLLM
from app.pipeline.comum import falas_para_contexto, formatar_falas
from app.schemas.llm import Fala, HipoteseIA, SugestoesGeradas, SugestoesIA
from app.schemas.sessao import Avaliacao

MAXIMO_HIPOTESES = 5
MAXIMO_PERGUNTAS = 10

SISTEMA = """\
Você é um preceptor ajudando um estudante de Medicina a estudar depois de uma simulação \
de anamnese. O estudante já escreveu as hipóteses dele; agora você sugere outras para \
ele estudar.

Regras:
- Nunca afirme diagnóstico. São hipóteses para estudo, não gabarito. Nunca diga que a \
hipótese do estudante está certa ou errada.
- Em sobre_hipoteses_aluno, comente cada hipótese do estudante, na mesma ordem e com o \
nome como ele escreveu: em a_favor, os dados da conversa que a apoiam; em contra, o que \
pesa contra ou o que ainda falta checar para avançar. Hipótese sindrômica (por exemplo, \
"gastroenterite aguda") é um bom começo: em contra, diga o que falta perguntar para \
chegar à causa.
- Em hipoteses, sugira de 2 a 5 hipóteses plausíveis para o que foi dito na conversa, \
diferentes das do estudante. Podem ser causas que cabem dentro de uma hipótese sindrômica \
dele. Para cada uma, liste em a_favor e contra só dados que apareceram na conversa, ou a \
falta de um dado importante ("não foi perguntado se...").
- Antes de escrever que algo não foi perguntado, leia a conversa inteira. Se o estudante \
perguntou, ou se a resposta do paciente já trouxe a informação (por exemplo, perguntou se \
quem comeu junto passou mal e o paciente disse que comeu sozinho), não diga que falta. \
Os itens já investigados vêm na mensagem.
- Português do Brasil, frases curtas, tom de preceptor, sem elogio vazio.
"""

REGRA_COM_PERGUNTAS = """\
- A queixa indicada ainda não tem checklist no app. Em perguntas_sugeridas, escreva até \
10 perguntas, como o estudante diria ao paciente, que a investigação dessa queixa pede e \
que não apareceram na conversa. Comece pelas mais úteis.
"""

REGRA_SEM_PERGUNTAS = """\
- Deixe perguntas_sugeridas como lista vazia: as queixas desta conversa já têm checklist.
"""


def queixas_sem_checklist(queixas_confirmadas: list[str], conteudo: Conteudo) -> list[str]:
    """Queixas confirmadas que não têm critério no app: 'outra' ou sem checklist."""
    return [q for q in queixas_confirmadas if q == QUEIXA_OUTRA or conteudo.checklist_da_queixa(q) is None]


def _nome_queixa(queixa_id: str, descricao_outra: str | None, conteudo: Conteudo) -> str | None:
    if queixa_id == QUEIXA_OUTRA:
        return descricao_outra or "queixa fora da biblioteca"
    queixa = conteudo.queixa(queixa_id)
    return queixa.nome if queixa is not None else None


def gerar_sugestoes(
    falas: list[Fala],
    queixas_confirmadas: list[str],
    descricao_outra: str | None,
    hipoteses_aluno: list[str],
    avaliacoes: list[Avaliacao],
    conteudo: Conteudo,
    llm: ClienteLLM,
) -> SugestoesIA:
    nomes_queixas = [n for q in queixas_confirmadas if (n := _nome_queixa(q, descricao_outra, conteudo))]
    ids_sem_checklist = queixas_sem_checklist(queixas_confirmadas, conteudo)
    sem_checklist = [n for q in ids_sem_checklist if (n := _nome_queixa(q, descricao_outra, conteudo))]
    pedir_perguntas = bool(ids_sem_checklist)
    faltantes = [{"id": a.item_id, "texto": a.texto} for a in avaliacoes if a.status == "faltou"]
    investigados = [a.texto for a in avaliacoes if a.status == "feito"]

    mensagem = (
        f"Queixa confirmada pelo estudante: {', '.join(nomes_queixas) or 'não informada'}.\n"
        + (f"Queixa sem checklist no app: {', '.join(sem_checklist) or 'não informada'}.\n" if pedir_perguntas else "")
        + f"\nHipóteses do estudante:\n{json.dumps(hipoteses_aluno, ensure_ascii=False)}\n\n"
        f"Itens do checklist já investigados (não diga que faltam):\n{json.dumps(investigados, ensure_ascii=False)}\n\n"
        f"Itens do checklist que faltaram:\n{json.dumps([f['texto'] for f in faltantes], ensure_ascii=False)}\n\n"
        f"Transcrição:\n<transcricao>\n{formatar_falas(falas)}\n</transcricao>"
    )
    resposta = llm.gerar(
        tarefa="sugestoes",
        sistema=SISTEMA + (REGRA_COM_PERGUNTAS if pedir_perguntas else REGRA_SEM_PERGUNTAS),
        mensagem=mensagem,
        saida=SugestoesGeradas,
        contexto={
            "falas": falas_para_contexto(falas),
            "queixas": nomes_queixas,
            "hipoteses_aluno": hipoteses_aluno,
            "itens_faltantes": faltantes,
            "pedir_perguntas": pedir_perguntas,
        },
    )
    hipoteses = _limpar(resposta.hipoteses)[:MAXIMO_HIPOTESES]
    # Uma análise por hipótese do aluno, no máximo; o nome é sempre o que ele escreveu.
    sobre_aluno = [
        h.model_copy(update={"nome": escrita})
        for h, escrita in zip(_limpar(resposta.sobre_hipoteses_aluno), hipoteses_aluno, strict=False)
    ]
    perguntas = [p.strip() for p in resposta.perguntas_sugeridas if p.strip()][:MAXIMO_PERGUNTAS]
    if not pedir_perguntas:
        perguntas = []  # a terceira camada só existe quando falta critério
    return SugestoesIA(hipoteses=hipoteses, perguntas_sugeridas=perguntas, sobre_hipoteses_aluno=sobre_aluno)


def _limpar(hipoteses: list[HipoteseIA]) -> list[HipoteseIA]:
    return [
        HipoteseIA(
            nome=h.nome.strip(),
            a_favor=[t.strip() for t in h.a_favor if t.strip()],
            contra=[t.strip() for t in h.contra if t.strip()],
        )
        for h in hipoteses
        if h.nome.strip()
    ]
