"""Voz do paciente pela IA (Piper), sem baixar modelo nenhum."""

import io
import wave
from pathlib import Path

import pytest

from app.config import Settings
from app.pipeline.voz import ErroVoz, VozEdge, VozPiper, obter_voz


class ModeloDeTeste:
    def __init__(self, nome: str) -> None:
        self.nome = nome
        self.textos: list[str] = []

    def synthesize_wav(self, texto: str, arquivo: wave.Wave_write) -> None:
        self.textos.append(texto)
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(22050)
        arquivo.writeframes(b"\x00\x00" * 100)


class VozComModelosDeTeste(VozPiper):
    def __init__(self, modelos: dict) -> None:
        super().__init__(modelos)
        self.carregados: list[Path] = []

    def _carregar(self, caminho: Path) -> ModeloDeTeste:
        self.carregados.append(caminho)
        return ModeloDeTeste(caminho.name)


def test_navegador_nao_usa_piper():
    assert obter_voz(Settings(_env_file=None)) is None


def test_piper_sem_arquivo_de_voz_fica_com_o_navegador(tmp_path):
    settings = Settings(_env_file=None, voz_paciente="piper", piper_voz_masculina=tmp_path / "nao-existe.onnx")
    assert obter_voz(settings) is None


def test_piper_com_as_vozes_dos_dois_sexos(tmp_path):
    for nome in ("homem.onnx", "mulher.onnx"):
        (tmp_path / nome).write_bytes(b"x")
    settings = Settings(
        _env_file=None,
        voz_paciente="piper",
        piper_voz_masculina=tmp_path / "homem.onnx",
        piper_voz_feminina=tmp_path / "mulher.onnx",
    )
    voz = obter_voz(settings)
    assert voz is not None
    assert voz.sexos == ["feminino", "masculino"]


def test_fala_vira_wav_com_a_voz_do_sexo_ou_a_outra():
    voz = VozComModelosDeTeste({"masculino": Path("homem.onnx")})
    wav = voz.falar("  Começou ontem à noite.  ", "feminino")
    with wave.open(io.BytesIO(wav)) as arquivo:
        assert arquivo.getframerate() == 22050
        assert arquivo.getnframes() == 100
    assert voz.carregados == [Path("homem.onnx")]


def test_fala_vazia_ou_que_falha_vira_erro_de_voz():
    voz = VozComModelosDeTeste({"masculino": Path("homem.onnx")})
    with pytest.raises(ErroVoz):
        voz.falar("   ", "masculino")

    class Quebrada(VozPiper):
        def _carregar(self, caminho):
            raise RuntimeError("modelo corrompido")

    with pytest.raises(ErroVoz):
        Quebrada({"feminino": Path("mulher.onnx")}).falar("Oi", "feminino")


def test_edge_usa_a_voz_do_sexo_e_devolve_mp3(monkeypatch):
    voz = obter_voz(Settings(_env_file=None, voz_paciente="edge"))
    assert isinstance(voz, VozEdge)
    assert voz.sexos == ["feminino", "masculino"]
    assert voz.tipo_audio == "audio/mpeg"
    pedidas: list[str] = []

    async def sintetizar(texto: str, nome: str) -> bytes:
        pedidas.append(nome)
        return b"ID3" + texto.encode()

    monkeypatch.setattr(VozEdge, "_sintetizar", staticmethod(sintetizar))
    assert voz.falar(" Dói aqui. ", "feminino") == "ID3Dói aqui.".encode()
    assert voz.falar("Dói aqui.", "masculino").startswith(b"ID3")
    assert pedidas == ["pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"]


def test_edge_sem_internet_vira_erro_de_voz(monkeypatch):
    async def sem_rede(texto: str, nome: str) -> bytes:
        raise OSError("sem conexão")

    monkeypatch.setattr(VozEdge, "_sintetizar", staticmethod(sem_rede))
    with pytest.raises(ErroVoz):
        VozEdge({"feminino": "pt-BR-FranciscaNeural"}).falar("Oi", "masculino")
