"""Hipóteses sugeridas para estudo e perguntas que ajudariam.

Roda só depois que o aluno escreveu as hipóteses dele. Nunca afirma diagnóstico
(regra 6): a interface mostra tudo como "sugestão, não gabarito". Fica fora da nota.
"""

import json

from app.conteudo import QUEIXA_OUTRA, Conteudo
from app.llm import ClienteLLM
from app.pipeline.comum import falas_para_contexto, formatar_falas
from app.schemas.llm import Fala, HipoteseIA, SugestoesIA
from app.schemas.sessao import Avaliacao

MAXIMO_HIPOTESES = 5
MAXIMO_PERGUNTAS = 10

SISTEMA = """\
Você é um preceptor ajudando um estudante de Medicina a estudar depois de uma simulação \
de anamnese. O estudante já escreveu as hipóteses dele; agora você sugere outras para \
ele estudar.

Regras:
- Nunca afirme diagnóstico. São hipóteses para estudo, não gabarito.
- Sugira de 2 a 5 hipóteses plausíveis para o que foi dito na conversa. Para cada uma, \
liste em a_favor e contra só dados que apareceram na conversa, ou a falta de um dado \
importante ("não foi perguntado se...").
- Em perguntas_sugeridas, escreva até 10 perguntas, como o estudante diria ao paciente, \
que ajudariam a diferenciar as hipóteses ou cobrir o que faltou. Comece pelas mais úteis.
- Português do Brasil, frases curtas, tom de preceptor, sem elogio vazio.
"""


def gerar_sugestoes(
    falas: list[Fala],
    queixas_confirmadas: list[str],
    descricao_outra: str | None,
    hipoteses_aluno: list[str],
    avaliacoes: list[Avaliacao],
    conteudo: Conteudo,
    llm: ClienteLLM,
) -> SugestoesIA:
    nomes_queixas = []
    for queixa_id in queixas_confirmadas:
        if queixa_id == QUEIXA_OUTRA:
            nomes_queixas.append(descricao_outra or "queixa fora da biblioteca")
        elif (queixa := conteudo.queixa(queixa_id)) is not None:
            nomes_queixas.append(queixa.nome)
    faltantes = [{"id": a.item_id, "texto": a.texto} for a in avaliacoes if a.status == "faltou"]

    mensagem = (
        f"Queixa confirmada pelo estudante: {', '.join(nomes_queixas) or 'não informada'}.\n\n"
        f"Hipóteses do estudante:\n{json.dumps(hipoteses_aluno, ensure_ascii=False)}\n\n"
        f"Itens do checklist que faltaram:\n{json.dumps([f['texto'] for f in faltantes], ensure_ascii=False)}\n\n"
        f"Transcrição:\n<transcricao>\n{formatar_falas(falas)}\n</transcricao>"
    )
    resposta = llm.gerar(
        tarefa="sugestoes",
        sistema=SISTEMA,
        mensagem=mensagem,
        saida=SugestoesIA,
        contexto={
            "falas": falas_para_contexto(falas),
            "queixas": nomes_queixas,
            "hipoteses_aluno": hipoteses_aluno,
            "itens_faltantes": faltantes,
        },
    )
    hipoteses = [
        HipoteseIA(
            nome=h.nome.strip(),
            a_favor=[t.strip() for t in h.a_favor if t.strip()],
            contra=[t.strip() for t in h.contra if t.strip()],
        )
        for h in resposta.hipoteses
        if h.nome.strip()
    ][:MAXIMO_HIPOTESES]
    perguntas = [p.strip() for p in resposta.perguntas_sugeridas if p.strip()][:MAXIMO_PERGUNTAS]
    return SugestoesIA(hipoteses=hipoteses, perguntas_sugeridas=perguntas)
