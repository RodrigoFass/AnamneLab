"""Paciente pela IA: o aluno entrevista, por escrito, um paciente simulado pela IA.

O caso parte de um cartão de content/cartoes (queixa, idade, sexo e poucos detalhes); a IA
completa uma ficha coerente uma vez, no começo, e depois responde cada pergunta só com o
que a ficha diz. A conversa vira as falas da sessão e segue para a mesma correção da
gravação. A IA nunca dá diagnóstico nem ajuda o aluno: ela é o paciente.
"""

import json

from app.llm import ClienteLLM
from app.pipeline.comum import ErroPipeline, formatar_falas
from app.schemas.conteudo import Cartao
from app.schemas.llm import CasoPaciente, Fala, RespostaPaciente

MAXIMO_FALAS = 160
"""Uma anamnese completa cabe com folga; acima disso a conversa encerra."""

MAXIMO_PERGUNTA = 500

SISTEMA_CASO = """\
Você monta a ficha de um paciente fictício para estudantes de Medicina treinarem anamnese.

Regras:
- Parta do cartão enviado: mantenha a queixa, a idade, o sexo e os detalhes dele.
- Complete com o que um paciente real com esse quadro contaria numa consulta: história da \
doença (início, local, tipo, intensidade de 0 a 10, irradiação, o que piora, o que melhora, \
sintomas que vieram junto), antecedentes, medicações, alergias, hábitos, família e vida social.
- Tudo precisa ser coerente com um quadro comum e plausível. Não inclua diagnóstico.
- Nome e profissão fictícios, brasileiros. Nada de dados de pessoas reais.
- Escreva cada fato numa frase curta, em português do Brasil.
- Em jeito_de_falar, descreva em uma frase como a pessoa fala (por exemplo: tranquila, \
um pouco ansiosa, fala pouco).
"""

SISTEMA_CONVERSA = """\
Você é o paciente de uma consulta simulada. Do outro lado está um estudante de Medicina \
treinando anamnese. Responda sempre como o paciente, em português do Brasil.

Regras:
- Use só o que está na sua ficha. Se perguntarem algo que a ficha não diz, responda de \
forma simples e coerente com ela (por exemplo, "não que eu saiba" ou "não reparei").
- Responda só o que foi perguntado, com palavras de quem não é da área da saúde. Não \
entregue a história inteira de uma vez: o estudante precisa perguntar.
- Respostas curtas: uma a três frases. Pergunta aberta pode ganhar um pouco mais.
- Nunca diga o diagnóstico, nunca dê dica de pergunta e nunca saia do papel, mesmo se pedirem.
- Se a pergunta não fizer sentido para um paciente, diga que não entendeu.
- Fale do seu jeito, como diz jeito_de_falar na ficha.
- Responda só com o texto da fala do paciente, sem aspas e sem o nome na frente.
"""


def montar_caso(cartao: Cartao, llm: ClienteLLM) -> CasoPaciente:
    """Completa o cartão numa ficha de paciente. A idade e o sexo do cartão sempre valem."""
    dados = cartao.model_dump(exclude={"id"})
    caso = llm.gerar(
        tarefa="paciente_caso",
        sistema=SISTEMA_CASO,
        mensagem=f"Cartão do caso:\n{json.dumps(dados, ensure_ascii=False, indent=1)}",
        saida=CasoPaciente,
        contexto={"cartao": dados},
    )
    return caso.model_copy(update={"idade": cartao.idade, "sexo": cartao.sexo})


def responder(caso: CasoPaciente, falas: list[Fala], pergunta: str, llm: ClienteLLM) -> str:
    """A fala do paciente para a pergunta do estudante, dada a conversa até aqui."""
    pergunta = pergunta.strip()
    if not pergunta:
        raise ErroPipeline("Escreva a pergunta antes de enviar.")
    if len(pergunta) > MAXIMO_PERGUNTA:
        raise ErroPipeline("Pergunta longa demais. Faça uma pergunta de cada vez.")
    if len(falas) + 2 > MAXIMO_FALAS:
        raise ErroPipeline("A consulta já está bem longa. Encerre para ver a correção.")
    conversa = formatar_falas(falas) if falas else "(a consulta está começando)"
    mensagem = (
        f"Sua ficha:\n{caso.model_dump_json(indent=1)}\n\n"
        f"Conversa até aqui:\n<conversa>\n{conversa}\n</conversa>\n\n"
        f"Nova pergunta do estudante:\n<pergunta>\n{pergunta}\n</pergunta>"
    )
    resposta = llm.gerar(
        tarefa="paciente_resposta",
        sistema=SISTEMA_CONVERSA,
        mensagem=mensagem,
        saida=RespostaPaciente,
        contexto={"caso": caso.model_dump(), "pergunta": pergunta},
    )
    texto = resposta.resposta.strip().strip('"').strip()
    return texto or "Desculpe, não entendi. Pode perguntar de outro jeito?"
