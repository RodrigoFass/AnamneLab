"""Detecta a queixa principal dentro da lista fechada de content/queixas.json.

O LLM só sugere; o backend descarta qualquer id fora da biblioteca (vira "outra") e o
aluno confirma antes da correção. Nunca se inventa queixa.
"""

import json

from app.conteudo import QUEIXA_OUTRA
from app.llm import ClienteLLM
from app.pipeline.comum import falas_para_contexto, formatar_falas
from app.schemas.conteudo import BibliotecaQueixas
from app.schemas.llm import Fala, QueixaDetectada

SISTEMA = """\
Você lê a transcrição de uma simulação de anamnese entre estudantes de Medicina e \
identifica a queixa principal do paciente.

Regras:
- Escolha só entre os ids da lista de queixas enviada. Use os sinônimos para reconhecer \
o jeito como o paciente fala.
- Se houver mais de uma queixa da lista, ponha a mais importante primeiro.
- Se nenhuma queixa da lista servir, responda ["outra"] e escreva em descricao_outra a \
queixa como o paciente disse, em poucas palavras. Nos outros casos, descricao_outra é null.
- Nunca crie um id novo.
- Em trecho, copie literalmente a fala do paciente que mostra a queixa principal.
"""


def detectar_queixa(falas: list[Fala], biblioteca: BibliotecaQueixas, llm: ClienteLLM) -> QueixaDetectada:
    lista = [{"id": q.id, "nome": q.nome, "sinonimos": q.sinonimos} for q in biblioteca.queixas]
    mensagem = (
        "Lista de queixas (escolha só entre estes ids ou 'outra'):\n"
        f"{json.dumps(lista, ensure_ascii=False, indent=1)}\n\n"
        f"Transcrição:\n<transcricao>\n{formatar_falas(falas)}\n</transcricao>"
    )
    resposta = llm.gerar(
        tarefa="queixa",
        sistema=SISTEMA,
        mensagem=mensagem,
        saida=QueixaDetectada,
        contexto={"falas": falas_para_contexto(falas), "queixas": lista},
    )
    return filtrar_queixa(resposta, {q.id for q in biblioteca.queixas})


def filtrar_queixa(resposta: QueixaDetectada, ids_validos: set[str]) -> QueixaDetectada:
    """Ids fora da biblioteca viram 'outra'; repetidos saem; 'outra' só fica sozinha; lista vazia vira ['outra']."""
    queixas: list[str] = []
    for queixa_id in resposta.queixas:
        queixa_id = queixa_id if queixa_id in ids_validos else QUEIXA_OUTRA
        if queixa_id not in queixas:
            queixas.append(queixa_id)
    if len(queixas) > 1 and QUEIXA_OUTRA in queixas:
        queixas.remove(QUEIXA_OUTRA)  # 'outra' vale sozinha: com queixa da lista, fica a da lista
    if not queixas:
        queixas = [QUEIXA_OUTRA]
    descricao = resposta.descricao_outra if QUEIXA_OUTRA in queixas else None
    descricao = descricao.strip() if descricao and descricao.strip() else None
    return QueixaDetectada(queixas=queixas, descricao_outra=descricao, trecho=resposta.trecho.strip())
