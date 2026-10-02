"""Transcrição do áudio (Whisper) e descarte do arquivo.

`transcrever_e_apagar` é a única porta de entrada do pipeline: o áudio é apagado em
`finally`, inclusive quando a transcrição falha. As bibliotecas pesadas (faster-whisper,
openai) só são importadas dentro das funções que as usam.
"""

import logging
import math
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.config import Settings
from app.schemas.conteudo import BibliotecaQueixas

logger = logging.getLogger(__name__)

ARQUIVO_EXEMPLO = Path(__file__).with_name("exemplo_transcricao.txt")

MENSAGEM_NAO_OUVIU = "Não deu para ouvir a gravação. Grave de novo num lugar mais calmo."
MENSAGEM_INDISPONIVEL = "Não deu para transcrever a gravação agora. Grave de novo em alguns minutos."
MENSAGEM_LONGA = "A gravação passou de {minutos} minutos. Grave de novo, num tempo menor."

LIMITE_TOKENS_DICA = 224
BYTES_POR_TOKEN = 2.5
"""Estimativa conservadora para português (acentos custam mais de um byte)."""


class ErroTranscricao(Exception):
    """Falha na transcrição. `mensagem` é mostrada ao aluno."""

    def __init__(self, mensagem: str = MENSAGEM_NAO_OUVIU) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


class Transcritor(ABC):
    nome: str = "base"

    @abstractmethod
    def transcrever(self, caminho: Path, *, dica: str = "") -> str:
        """Texto corrido do áudio. `dica` lista termos esperados (nomes das queixas)."""


class TranscritorFalso(Transcritor):
    """Devolve a transcrição de exemplo, para desenvolver sem microfone nem Whisper."""

    nome = "falso"

    def transcrever(self, caminho: Path, *, dica: str = "") -> str:
        return ARQUIVO_EXEMPLO.read_text(encoding="utf-8")


class TranscritorLocal(Transcritor):
    """faster-whisper na máquina. O modelo é carregado na primeira gravação."""

    nome = "local"

    def __init__(self, modelo: str, duracao_maxima_min: int) -> None:
        self._nome_modelo = modelo
        self._duracao_maxima_min = duracao_maxima_min
        self._modelo: Any = None
        self._trava = threading.Lock()

    def _carregar(self) -> Any:
        with self._trava:
            if self._modelo is None:
                from faster_whisper import WhisperModel

                self._modelo = WhisperModel(self._nome_modelo, device="auto", compute_type="int8")
            return self._modelo

    def transcrever(self, caminho: Path, *, dica: str = "") -> str:
        modelo = self._carregar()
        segmentos, info = modelo.transcribe(str(caminho), language="pt", initial_prompt=dica or None, vad_filter=True)
        if info.duration > self._duracao_maxima_min * 60:
            raise ErroTranscricao(MENSAGEM_LONGA.format(minutos=self._duracao_maxima_min))
        return " ".join(segmento.text.strip() for segmento in segmentos).strip()


class TranscritorAPI(Transcritor):
    """API whisper-1. Só a transcrição usa esta API; a correção usa o provedor de LLM."""

    nome = "api"

    def __init__(self, chave: str | None, duracao_maxima_min: int) -> None:
        self._chave = chave
        self._duracao_maxima_min = duracao_maxima_min

    def transcrever(self, caminho: Path, *, dica: str = "") -> str:
        import openai

        cliente = openai.OpenAI(api_key=self._chave)
        try:
            with caminho.open("rb") as arquivo:
                resposta = cliente.audio.transcriptions.create(
                    model="whisper-1",
                    file=arquivo,
                    language="pt",
                    prompt=dica,
                    response_format="verbose_json",
                )
        except openai.APIConnectionError:
            logger.warning("sem conexão com a API de transcrição")
            raise ErroTranscricao(MENSAGEM_INDISPONIVEL) from None
        except openai.APIStatusError as erro:
            logger.warning("API de transcrição respondeu com erro HTTP %s", erro.status_code)
            raise ErroTranscricao(MENSAGEM_INDISPONIVEL) from None
        duracao = getattr(resposta, "duration", None)
        if duracao and duracao > self._duracao_maxima_min * 60:
            raise ErroTranscricao(MENSAGEM_LONGA.format(minutos=self._duracao_maxima_min))
        return (resposta.text or "").strip()


def obter_transcritor(settings: Settings) -> Transcritor:
    if settings.transcricao == "local":
        return TranscritorLocal(settings.whisper_modelo_local, settings.duracao_maxima_min)
    if settings.transcricao == "api":
        chave = settings.openai_api_key
        return TranscritorAPI(chave.get_secret_value() if chave else None, settings.duracao_maxima_min)
    return TranscritorFalso()


def _estimar_tokens(texto: str) -> int:
    return math.ceil(len(texto.encode("utf-8")) / BYTES_POR_TOKEN)


def montar_dica(queixas: BibliotecaQueixas, limite_tokens: int = LIMITE_TOKENS_DICA) -> str:
    """Dica para o Whisper: contexto curto + nomes e sinônimos das queixas, até ~224 tokens."""
    dica = "Simulação de anamnese em português entre estudante de Medicina e paciente."
    termos: list[str] = []
    for queixa in queixas.queixas:
        for termo in [queixa.nome, *queixa.sinonimos]:
            if termo.casefold() not in {t.casefold() for t in termos}:
                termos.append(termo)
    incluidos: list[str] = []
    for termo in termos:
        candidato = f"{dica} Termos: {', '.join([*incluidos, termo])}."
        if _estimar_tokens(candidato) > limite_tokens:
            break
        incluidos.append(termo)
    return f"{dica} Termos: {', '.join(incluidos)}." if incluidos else dica


def apagar_audio(caminho: Path) -> None:
    try:
        Path(caminho).unlink(missing_ok=True)
    except OSError:
        # Sem o caminho no log: só o fato.
        logger.error("não deu para apagar um áudio temporário")


PERGUNTAS_EXEMPLO = (
    "Bom dia, eu sou estudante de Medicina. Qual é o seu nome?",
    "O que te traz aqui hoje?",
    "Quando isso começou?",
    "Tem mais alguma coisa que o senhor ou a senhora sentiu junto?",
    "Toma algum remédio?",
)
"""Perguntas do modo de demonstração, uma por fala gravada, para a conversa andar sem Whisper."""


def transcrever_pergunta_e_apagar(caminho: Path, transcritor: Transcritor, *, numero: int, dica: str = "") -> str:
    """A pergunta falada ao paciente pela IA. No modo de demonstração, uma pergunta de exemplo."""
    if isinstance(transcritor, TranscritorFalso):
        apagar_audio(caminho)
        return PERGUNTAS_EXEMPLO[numero % len(PERGUNTAS_EXEMPLO)]
    return transcrever_e_apagar(caminho, transcritor, dica=dica)


def transcrever_e_apagar(caminho: Path, transcritor: Transcritor, *, dica: str = "") -> str:
    """Transcreve e SEMPRE apaga o áudio, inclusive em falha."""
    try:
        try:
            texto = transcritor.transcrever(Path(caminho), dica=dica)
        except ErroTranscricao:
            raise
        except Exception as erro:
            logger.warning("falha na transcrição (%s)", type(erro).__name__)
            raise ErroTranscricao(MENSAGEM_NAO_OUVIU) from None
        if not texto.strip():
            raise ErroTranscricao(MENSAGEM_NAO_OUVIU)
        return texto
    finally:
        apagar_audio(caminho)
