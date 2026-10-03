import pytest

from app.llm.falso import ClienteFalso
from app.pipeline.comum import ErroPipeline
from app.pipeline.paciente_ia import MAXIMO_EXAMES, MAXIMO_FALAS, examinar, montar_caso, responder
from app.schemas.conteudo import Cartao
from app.schemas.llm import Fala
from app.schemas.sessao import ExameFeito

CARTAO = Cartao(
    id="teste",
    queixa="cefaleia",
    idade=34,
    sexo="feminino",
    resumo="Dor de cabeça forte desde ontem.",
    detalhes=["Piora com a luz."],
)


class FalsoQueMudaIdade(ClienteFalso):
    def _gerar_json(self, *, tarefa, **kwargs) -> str:
        texto = super()._gerar_json(tarefa=tarefa, **kwargs)
        return texto.replace('"idade":34', '"idade":70').replace('"feminino"', '"masculino"')


def test_ficha_mantem_idade_e_sexo_do_cartao():
    caso = montar_caso(CARTAO, FalsoQueMudaIdade())
    assert (caso.idade, caso.sexo) == (34, "feminino")
    assert "Piora com a luz." in caso.historia_da_doenca


def test_responde_pelo_caso():
    caso = montar_caso(CARTAO, ClienteFalso())
    resposta = responder(caso, [], "Qual é o seu nome?", ClienteFalso())
    assert (resposta.resposta, resposta.proximo, resposta.nota_guia) == (f"Meu nome é {caso.nome}.", "seguir", "")
    assert responder(caso, [], "O que te traz aqui?", ClienteFalso()).resposta == CARTAO.resumo


def test_ficha_traz_exame_fisico():
    caso = montar_caso(CARTAO, ClienteFalso())
    assert caso.sinais_vitais and caso.exame_fisico


def test_paciente_anuncia_exame_e_se_despede():
    caso = montar_caso(CARTAO, ClienteFalso())
    assert responder(caso, [], "Agora vou examinar a senhora.", ClienteFalso()).proximo == "exame_fisico"
    assert responder(caso, [], "Pode ir, tchau!", ClienteFalso()).proximo == "despedida"


def test_paciente_estranha_noticia_grave_e_guia_comenta():
    caso = montar_caso(CARTAO, ClienteFalso())
    resposta = responder(caso, [], "A senhora tem 24 horas de vida.", ClienteFalso())
    assert resposta.proximo == "seguir"
    assert "?" in resposta.resposta  # questiona em vez de aceitar
    assert resposta.nota_guia


def test_exame_usa_a_ficha():
    caso = montar_caso(CARTAO, ClienteFalso())
    assert "bulhas" in examinar(caso, [], "Ausculta cardíaca", ClienteFalso())
    assert "FC" in examinar(caso, [], "Sinais vitais", ClienteFalso())
    with pytest.raises(ErroPipeline):
        examinar(caso, [], "  ", ClienteFalso())
    cheio = [ExameFeito(pedido="Abdome", achado="Normal.")] * MAXIMO_EXAMES
    with pytest.raises(ErroPipeline, match="Encerre"):
        examinar(caso, cheio, "Pulmões", ClienteFalso())


def test_ficha_antiga_sem_exame_continua_valida():
    dados = montar_caso(CARTAO, ClienteFalso()).model_dump(exclude={"sinais_vitais", "exame_fisico"})
    assert type(montar_caso(CARTAO, ClienteFalso())).model_validate(dados).exame_fisico == []


def test_recusa_pergunta_vazia_longa_ou_conversa_cheia():
    caso = montar_caso(CARTAO, ClienteFalso())
    with pytest.raises(ErroPipeline):
        responder(caso, [], "  ", ClienteFalso())
    with pytest.raises(ErroPipeline):
        responder(caso, [], "x" * 1001, ClienteFalso())
    cheia = [Fala(papel="entrevistador", texto="Oi?")] * MAXIMO_FALAS
    with pytest.raises(ErroPipeline, match="Encerre"):
        responder(caso, cheia, "E agora?", ClienteFalso())
