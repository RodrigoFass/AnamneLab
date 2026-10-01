"""Separa a transcrição corrida em falas do entrevistador e do paciente."""

import re

from app.llm import ClienteLLM
from app.pipeline.comum import ErroPipeline
from app.schemas.llm import Fala, FalasRotuladas

SISTEMA = """\
Você recebe a transcrição automática de uma simulação de consulta entre dois estudantes \
de Medicina: um faz o papel de médico (entrevistador) e o outro, de paciente.

Separe o texto em falas, na ordem em que aconteceram, e diga quem disse cada uma:
- "entrevistador": quem pergunta, conduz e explica.
- "paciente": quem conta o que sente e responde.

Regras:
- Copie o texto de cada fala exatamente como está na transcrição. Não corrija, não resuma, \
não traduza e não acrescente nada.
- Se a transcrição já trouxer marcas como "Médico:" ou "Paciente:", use-as para decidir o \
papel e não copie a marca para o texto.
- Uma pergunta e a resposta a ela são falas separadas.
- Não deixe nenhum trecho da transcrição de fora.
"""

MENSAGEM_VAZIA = "Não deu para ouvir a gravação. Grave de novo num lugar mais calmo."


def rotular_falas(texto: str, llm: ClienteLLM) -> list[Fala]:
    if not texto.strip():
        raise ErroPipeline(MENSAGEM_VAZIA)
    resposta = llm.gerar(
        tarefa="rotular",
        sistema=SISTEMA,
        mensagem=f"Transcrição:\n<transcricao>\n{texto}\n</transcricao>",
        saida=FalasRotuladas,
        contexto={"texto": texto},
    )
    falas = [Fala(papel=f.papel, texto=f.texto.strip()) for f in resposta.falas if f.texto.strip()]
    if not falas:
        raise ErroPipeline(MENSAGEM_VAZIA)
    return falas


_FRASE = re.compile(r"[^.?!]+[.?!]*")


def rotular_simples(texto: str) -> list[Fala]:
    """Plano B sem LLM: uma fala por frase; frase com '?' é do entrevistador.

    Usado quando o LLM falha depois da transcrição, para não perder a gravação (o áudio
    já foi apagado). O aluno corrige quem disse o quê antes de confirmar a queixa.
    """
    falas: list[Fala] = []
    for frase in (f.strip() for f in _FRASE.findall(texto)):
        if not frase:
            continue
        papel = "entrevistador" if frase.endswith("?") else "paciente"
        if falas and falas[-1].papel == papel:
            falas[-1] = Fala(papel=papel, texto=f"{falas[-1].texto} {frase}")
        else:
            falas.append(Fala(papel=papel, texto=frase))
    return falas
