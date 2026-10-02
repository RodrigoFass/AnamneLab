"""Voz do paciente pela IA: o texto da resposta vira fala.

Com VOZ_PACIENTE=piper, o backend fala com o Piper, uma voz neural que roda na máquina,
grátis e sem internet. Cada voz é um arquivo .onnx (com o .onnx.json ao lado), um por sexo
do paciente. Sem o Piper, quem fala é o navegador (speechSynthesis), no próprio aparelho.
A biblioteca piper-tts só é importada aqui dentro, quando a primeira fala é pedida.
"""

import io
import logging
import threading
import wave
from pathlib import Path
from typing import Any

from app.config import Settings
from app.schemas.sessao import SexoPaciente

logger = logging.getLogger(__name__)

MAXIMO_TEXTO = 2000
"""Uma resposta do paciente tem poucas frases; acima disso, algo está errado."""


class ErroVoz(Exception):
    """A voz não saiu. O aluno continua lendo a resposta na tela."""


class VozPiper:
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


def obter_voz(settings: Settings) -> VozPiper | None:
    """A voz do backend, ou None quando quem fala é o navegador."""
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
