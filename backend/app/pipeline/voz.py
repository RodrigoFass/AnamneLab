"""Voz do paciente pela IA: o texto da resposta vira fala.

- VOZ_PACIENTE=edge: vozes neurais da Microsoft (as do "Ler em voz alta" do Edge), grátis e
  sem chave, com voz de homem e de mulher em português do Brasil. Precisa de internet, e o
  texto da fala (do paciente fictício) passa pelo serviço da Microsoft.
- VOZ_PACIENTE=piper: o Piper, que roda na máquina, grátis e sem internet. Cada voz é um
  arquivo .onnx (com o .onnx.json ao lado). Soa mais robótico e só tem vozes masculinas em pt-BR.
- Sem nenhum dos dois, quem fala é o navegador (speechSynthesis), no próprio aparelho.

As bibliotecas (edge-tts, piper-tts) só são importadas aqui dentro, na primeira fala.
"""

import asyncio
import io
import logging
import threading
import wave
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.config import Settings
from app.schemas.sessao import SexoPaciente

logger = logging.getLogger(__name__)

MAXIMO_TEXTO = 2000
"""Uma resposta do paciente tem poucas frases; acima disso, algo está errado."""


class ErroVoz(Exception):
    """A voz não saiu. O aluno continua lendo a resposta na tela."""


class VozPaciente(ABC):
    """Uma voz por sexo do paciente. Sem a voz de um sexo, usa a outra que houver."""

    tipo_audio: str = "audio/wav"

    @property
    @abstractmethod
    def sexos(self) -> list[SexoPaciente]: ...

    @abstractmethod
    def falar(self, texto: str, sexo: SexoPaciente) -> bytes:
        """O áudio da fala, no formato `tipo_audio`. Falha vira ErroVoz."""


class VozEdge(VozPaciente):
    """Vozes neurais do Edge pela biblioteca edge-tts. Devolve MP3."""

    tipo_audio = "audio/mpeg"

    def __init__(self, vozes: dict[SexoPaciente, str]) -> None:
        self._vozes = {sexo: voz for sexo, voz in vozes.items() if voz}

    @property
    def sexos(self) -> list[SexoPaciente]:
        return sorted(self._vozes)

    def falar(self, texto: str, sexo: SexoPaciente) -> bytes:
        texto = texto.strip()[:MAXIMO_TEXTO]
        voz = self._vozes.get(sexo) or next(iter(self._vozes.values()), None)
        if not texto or voz is None:
            raise ErroVoz
        try:
            audio = asyncio.run(self._sintetizar(texto, voz))
        except Exception as erro:
            # Sem o texto no log: só o tipo do erro.
            logger.warning("voz do paciente (edge) falhou (%s)", type(erro).__name__)
            raise ErroVoz from None
        if not audio:
            raise ErroVoz
        return audio

    @staticmethod
    async def _sintetizar(texto: str, voz: str) -> bytes:
        import edge_tts

        partes: list[bytes] = []
        async for pedaco in edge_tts.Communicate(texto, voz).stream():
            if pedaco.get("type") == "audio" and pedaco.get("data"):
                partes.append(pedaco["data"])
        return b"".join(partes)


class VozPiper(VozPaciente):
    """Piper na máquina. Cada modelo é carregado na primeira fala daquele sexo."""

    def __init__(self, modelos: dict[SexoPaciente, Path]) -> None:
        self._modelos = modelos
        self._carregados: dict[Path, Any] = {}
        self._trava = threading.Lock()

    @property
    def sexos(self) -> list[SexoPaciente]:
        return sorted(self._modelos)

    def _carregar(self, caminho: Path) -> Any:
        with self._trava:
            if caminho not in self._carregados:
                from piper import PiperVoice

                self._carregados[caminho] = PiperVoice.load(str(caminho))
            return self._carregados[caminho]

    def falar(self, texto: str, sexo: SexoPaciente) -> bytes:
        """WAV com a fala. Sem voz para o sexo pedido, usa a outra que houver."""
        texto = texto.strip()[:MAXIMO_TEXTO]
        caminho = self._modelos.get(sexo) or next(iter(self._modelos.values()), None)
        if not texto or caminho is None:
            raise ErroVoz
        try:
            voz = self._carregar(caminho)
            saida = io.BytesIO()
            with wave.open(saida, "wb") as arquivo:
                voz.synthesize_wav(texto, arquivo)
            return saida.getvalue()
        except Exception as erro:
            # Sem o texto no log: só o tipo do erro.
            logger.warning("voz do paciente falhou (%s)", type(erro).__name__)
            raise ErroVoz from None


def obter_voz(settings: Settings) -> VozPaciente | None:
    """A voz do backend, ou None quando quem fala é o navegador."""
    if settings.voz_paciente == "edge":
        return VozEdge({"masculino": settings.edge_voz_masculina, "feminino": settings.edge_voz_feminina})
    if settings.voz_paciente != "piper":
        return None
    modelos: dict[SexoPaciente, Path] = {}
    for sexo, caminho in (("masculino", settings.piper_voz_masculina), ("feminino", settings.piper_voz_feminina)):
        if caminho is None:
            continue
        if caminho.is_file():
            modelos[sexo] = caminho
        else:
            logger.warning("voz do Piper não encontrada para o sexo %s; confira o .env", sexo)
    return VozPiper(modelos) if modelos else None
