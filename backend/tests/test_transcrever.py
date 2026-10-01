from pathlib import Path

import pytest

from app.pipeline.transcrever import (
    ARQUIVO_EXEMPLO,
    MENSAGEM_NAO_OUVIU,
    ErroTranscricao,
    Transcritor,
    TranscritorFalso,
    _estimar_tokens,
    montar_dica,
    transcrever_e_apagar,
)


class TranscritorQueFalha(Transcritor):
    def __init__(self, erro: Exception) -> None:
        self.erro = erro

    def transcrever(self, caminho: Path, *, dica: str = "") -> str:
        assert caminho.exists()  # o arquivo existe durante a transcrição
        raise self.erro


class TranscritorVazio(Transcritor):
    def transcrever(self, caminho: Path, *, dica: str = "") -> str:
        return "   "


@pytest.fixture
def audio(tmp_path: Path) -> Path:
    caminho = tmp_path / "anamnelab-teste.webm"
    caminho.write_bytes(b"\x1a\x45\xdf\xa3 audio de teste")
    return caminho


def test_apaga_o_audio_no_sucesso(audio):
    texto = transcrever_e_apagar(audio, TranscritorFalso())
    assert "Médico:" in texto
    assert not audio.exists()


def test_apaga_o_audio_quando_a_transcricao_quebra(audio):
    with pytest.raises(ErroTranscricao) as erro:
        transcrever_e_apagar(audio, TranscritorQueFalha(RuntimeError("modelo não carregou")))
    assert erro.value.mensagem == MENSAGEM_NAO_OUVIU
    assert not audio.exists()


def test_apaga_o_audio_com_erro_de_transcricao_proprio(audio):
    with pytest.raises(ErroTranscricao) as erro:
        transcrever_e_apagar(audio, TranscritorQueFalha(ErroTranscricao("A gravação passou de 20 minutos.")))
    assert erro.value.mensagem == "A gravação passou de 20 minutos."
    assert not audio.exists()


def test_apaga_o_audio_quando_nada_foi_ouvido(audio):
    with pytest.raises(ErroTranscricao):
        transcrever_e_apagar(audio, TranscritorVazio())
    assert not audio.exists()


def test_arquivo_que_ja_sumiu_nao_quebra(tmp_path):
    texto = transcrever_e_apagar(tmp_path / "anamnelab-sumiu.webm", TranscritorFalso())
    assert texto


def test_transcricao_de_exemplo():
    linhas = [linha for linha in ARQUIVO_EXEMPLO.read_text(encoding="utf-8").splitlines() if linha.strip()]
    assert 40 <= len(linhas) <= 60
    assert all(linha.startswith(("Médico:", "Paciente:")) for linha in linhas)


def test_dica_respeita_o_limite_de_tokens(conteudo):
    dica = montar_dica(conteudo.queixas)
    assert "Dor torácica" in dica and "dor no peito" in dica
    assert _estimar_tokens(dica) <= 224
    curta = montar_dica(conteudo.queixas, limite_tokens=40)
    assert _estimar_tokens(curta) <= 40
