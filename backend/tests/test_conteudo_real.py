"""O único teste que lê o content/ de verdade (e os JSON Schemas de content/schema/)."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.conteudo import carregar_conteudo
from app.llm.falso import ClienteFalso
from app.pipeline.corrigir import corrigir
from app.pipeline.queixa import detectar_queixa
from app.pipeline.rotular_falas import rotular_falas
from app.pipeline.transcrever import TranscritorFalso
from tests.apoio import PASTA_FIXTURES

PASTA_CONTEUDO = Path(__file__).resolve().parents[2] / "content"
PASTA_SCHEMA = PASTA_CONTEUDO / "schema"
NECESSARIOS = [
    "queixas.json",
    "termo-gravacao.json",
    "checklists/geral.json",
    "cartoes/cartoes.json",
]

faltando = [n for n in NECESSARIOS if not (PASTA_CONTEUDO / n).is_file()]


def _validador(nome: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((PASTA_SCHEMA / nome).read_text(encoding="utf-8")))


def _erros(validador: Draft202012Validator, caminho: Path) -> list[str]:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return [f"{caminho.name}: {e.message}" for e in validador.iter_errors(dados)]


def _conferir_pasta(pasta: Path) -> list[str]:
    erros = _erros(_validador("queixas.schema.json"), pasta / "queixas.json")
    erros += _erros(_validador("cartao.schema.json"), pasta / "cartoes" / "cartoes.json")
    for arquivo in sorted((pasta / "checklists").glob("*.json")):
        erros += _erros(_validador("checklist.schema.json"), arquivo)
    return erros


@pytest.mark.skipif(not PASTA_SCHEMA.is_dir(), reason="content/schema ainda não existe")
def test_fixtures_seguem_os_json_schemas():
    assert _conferir_pasta(PASTA_FIXTURES) == []


@pytest.mark.skipif(bool(faltando), reason=f"content/ ainda sem: {', '.join(faltando)}")
class TestConteudoReal:
    def test_segue_os_json_schemas(self):
        assert _conferir_pasta(PASTA_CONTEUDO) == []

    def test_carrega_com_os_modelos_do_backend(self):
        conteudo = carregar_conteudo(PASTA_CONTEUDO)
        assert conteudo.checklist_geral.id == "geral"
        assert conteudo.termo.versao
        assert conteudo.queixas.queixas
        assert conteudo.cartoes.cartoes
        dor = conteudo.checklist_da_queixa("dor-toracica")
        assert dor is not None and dor.tipo == "queixa"

    def test_correcao_falsa_roda_na_transcricao_de_exemplo(self):
        conteudo = carregar_conteudo(PASTA_CONTEUDO)
        llm = ClienteFalso()
        falas = rotular_falas(TranscritorFalso().transcrever(Path("exemplo")), llm)
        assert 40 <= len(falas) <= 60
        detectada = detectar_queixa(falas, conteudo.queixas, llm)
        # Falta de ar e inchaço aparecem depois, no interrogatório: não viram queixa principal.
        assert detectada.queixas == ["dor-toracica"]
        resultado = corrigir(falas, ["dor-toracica"], conteudo, llm, contar_rascunho=True)
        ids = [a.item_id for a in resultado.avaliacoes]
        assert len(ids) == len(set(ids))
        feitos = sum(a.status == "feito" for a in resultado.avaliacoes)
        # A transcrição de exemplo cumpre uns 2/3 dos itens.
        assert 0.5 <= feitos / len(ids) <= 0.8, f"{feitos} de {len(ids)}"
        assert resultado.notas.provisoria is (any(c.status == "rascunho" for c in resultado.checklists_usados))

    def test_toda_queixa_da_biblioteca_tem_checklist(self):
        conteudo = carregar_conteudo(PASTA_CONTEUDO)
        for queixa in conteudo.queixas.queixas:
            checklist = conteudo.checklist_da_queixa(queixa.id)
            assert checklist is not None, queixa.id
            assert checklist.tipo == "queixa" and checklist.queixa == queixa.id

    @pytest.mark.parametrize(
        "queixa",
        ["dispneia", "dor-abdominal", "cefaleia", "febre", "tosse", "dor-lombar", "sincope", "edema", "diarreia"],
    )
    def test_correcao_falsa_roda_com_cada_queixa(self, queixa):
        conteudo = carregar_conteudo(PASTA_CONTEUDO)
        llm = ClienteFalso()
        falas = rotular_falas(TranscritorFalso().transcrever(Path("exemplo")), llm)
        resultado = corrigir(falas, [queixa], conteudo, llm, contar_rascunho=True)
        assert [c.id for c in resultado.checklists_usados] == ["geral", queixa]
        ids_da_queixa = {i.id for s in conteudo.checklist_da_queixa(queixa).secoes for i in s.itens}
        avaliados = {a.item_id for a in resultado.avaliacoes}
        assert ids_da_queixa <= avaliados
        assert resultado.notas.geral is not None and resultado.notas.queixa is not None
