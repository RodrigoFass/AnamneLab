import pytest

from app.llm.falso import ClienteFalso
from app.pipeline.comum import ErroPipeline
from app.pipeline.paciente_ia import MAXIMO_FALAS, montar_caso, responder
from app.schemas.conteudo import Cartao
from app.schemas.llm import Fala

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
    assert responder(caso, [], "Qual é o seu nome?", ClienteFalso()) == f"Meu nome é {caso.nome}."
    assert responder(caso, [], "O que te traz aqui?", ClienteFalso()) == CARTAO.resumo


def test_recusa_pergunta_vazia_longa_ou_conversa_cheia():
    caso = montar_caso(CARTAO, ClienteFalso())
    with pytest.raises(ErroPipeline):
        responder(caso, [], "  ", ClienteFalso())
    with pytest.raises(ErroPipeline):
        responder(caso, [], "x" * 501, ClienteFalso())
    cheia = [Fala(papel="entrevistador", texto="Oi?")] * MAXIMO_FALAS
    with pytest.raises(ErroPipeline, match="Encerre"):
        responder(caso, cheia, "E agora?", ClienteFalso())
