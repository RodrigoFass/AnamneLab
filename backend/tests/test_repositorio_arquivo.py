import json
from datetime import UTC, datetime

import pytest

from app.config import Settings
from app.repositorio import obter_repositorio
from app.repositorio.arquivo import MENSAGEM_INTERROMPIDA, ErroArquivoHistorico, RepositorioArquivo
from app.schemas.llm import Fala
from app.schemas.sessao import Consentimento, Sessao


def _sessao(sessao_id: str = "s1", status: str = "criada") -> Sessao:
    return Sessao(
        id=sessao_id,
        dono_id="aluno",
        criada_em=datetime(2026, 10, 2, 7, tzinfo=UTC),
        status=status,
        origem_caso="inventado",
    )


@pytest.fixture
def caminho(tmp_path):
    return tmp_path / "dados" / "historico.json"


def test_historico_continua_depois_de_fechar_o_app(caminho):
    repo = RepositorioArquivo(caminho)
    repo.criar_sessao(_sessao())
    repo.adicionar_consentimento(
        Consentimento(
            id="c1",
            sessao_id="s1",
            papel="paciente",
            nome_informado="Colega",
            versao_termo="2",
            aceito_em=datetime(2026, 10, 2, 7, 1, tzinfo=UTC),
        )
    )
    repo.salvar_transcricao("s1", [Fala(papel="entrevistador", texto="O senhor fuma?")], editada=False)
    repo.atualizar_sessao("s1", status="aguardando_queixa", progresso=100)
    repo.registrar_queixa_outra("Dor no dedão")

    reaberto = RepositorioArquivo(caminho)
    sessao = reaberto.obter_sessao("s1")
    assert sessao == repo.obter_sessao("s1")
    assert sessao.status == "aguardando_queixa"
    assert sessao.falas[0].texto == "O senhor fuma?"
    assert len(sessao.consentimentos) == 1
    assert [s.id for s in reaberto.listar_sessoes("aluno")] == ["s1"]
    assert reaberto.fila_queixas == repo.fila_queixas
    assert [p.name for p in caminho.parent.iterdir()] == ["historico.json"]  # sem temporário sobrando


def test_excluir_tira_a_sessao_do_arquivo(caminho):
    repo = RepositorioArquivo(caminho)
    repo.criar_sessao(_sessao())
    repo.salvar_transcricao("s1", [Fala(papel="paciente", texto="Texto que precisa sumir.")], editada=False)
    repo.apagar_sessao("s1")
    assert "Texto que precisa sumir" not in caminho.read_text(encoding="utf-8")
    assert RepositorioArquivo(caminho).obter_sessao("s1") is None


@pytest.mark.parametrize("status", ["processando_audio", "corrigindo", "gerando_sugestoes"])
def test_etapa_interrompida_volta_como_erro_para_tentar_de_novo(caminho, status):
    RepositorioArquivo(caminho).criar_sessao(_sessao(status=status))
    sessao = RepositorioArquivo(caminho).obter_sessao("s1")
    assert sessao.status == "erro"
    assert sessao.mensagem_erro == MENSAGEM_INTERROMPIDA
    # O arquivo também já fica com o erro.
    assert json.loads(caminho.read_text(encoding="utf-8"))["sessoes"][0]["status"] == "erro"


def test_sessao_concluida_nao_muda_ao_reabrir(caminho):
    RepositorioArquivo(caminho).criar_sessao(_sessao(status="concluida"))
    assert RepositorioArquivo(caminho).obter_sessao("s1").status == "concluida"


@pytest.mark.parametrize("conteudo", ["{ quebrado", "[]", '{"sessoes": 3}'])
def test_arquivo_ilegivel_para_o_app_sem_apagar_nada(caminho, conteudo):
    caminho.parent.mkdir(parents=True)
    caminho.write_text(conteudo, encoding="utf-8")
    with pytest.raises(ErroArquivoHistorico):
        RepositorioArquivo(caminho)
    assert caminho.read_text(encoding="utf-8") == conteudo


def test_sessao_de_outra_versao_volta_ao_arquivo_como_estava(caminho):
    estranha = {"id": "velha", "formato": "antigo"}
    caminho.parent.mkdir(parents=True)
    caminho.write_text(json.dumps({"versao": 1, "sessoes": [estranha]}), encoding="utf-8")
    repo = RepositorioArquivo(caminho)
    assert repo.obter_sessao("velha") is None
    repo.criar_sessao(_sessao())
    assert estranha in json.loads(caminho.read_text(encoding="utf-8"))["sessoes"]


def test_fabrica_usa_o_arquivo_configurado(caminho):
    settings = Settings(_env_file=None, banco="arquivo", arquivo_historico=caminho)
    repo = obter_repositorio(settings)
    assert isinstance(repo, RepositorioArquivo)
    repo.criar_sessao(_sessao())
    assert caminho.exists()
