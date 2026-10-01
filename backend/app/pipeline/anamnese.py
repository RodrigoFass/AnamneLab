"""Monta a anamnese estruturada a partir das falas."""

from app.llm import ClienteLLM
from app.pipeline.comum import falas_para_contexto, formatar_falas
from app.schemas.llm import AnamneseEstruturada, Fala

NAO_ABORDADO = "Não abordado."

SISTEMA = f"""\
Você organiza a transcrição de uma simulação de anamnese, feita por estudantes de \
Medicina, no formato clássico de anamnese em português do Brasil.

Regras:
- Use só o que foi dito na conversa. Não suponha, não complete e não interprete exames.
- Não dê diagnóstico nem hipótese diagnóstica.
- Escreva em terceira pessoa, frases curtas, linguagem técnica simples.
- Campo que não foi abordado na conversa recebe exatamente "{NAO_ABORDADO}".
- identificacao: nome, idade, profissão e o que mais foi dito sobre quem é o paciente.
- queixa_principal: a queixa nas palavras do paciente, com o tempo de duração se foi dito.
- hda: história da doença atual, em ordem cronológica.
"""


def montar_anamnese(falas: list[Fala], llm: ClienteLLM) -> AnamneseEstruturada:
    resposta = llm.gerar(
        tarefa="anamnese",
        sistema=SISTEMA,
        mensagem=f"Transcrição:\n<transcricao>\n{formatar_falas(falas)}\n</transcricao>",
        saida=AnamneseEstruturada,
        contexto={"falas": falas_para_contexto(falas)},
    )
    campos = {nome: (valor.strip() or NAO_ABORDADO) for nome, valor in resposta.model_dump().items()}
    return AnamneseEstruturada(**campos)
