"""Repositório num arquivo JSON no computador, para o protótipo guardar o histórico sem Supabase.

Guarda o mesmo que o banco guardaria (consentimentos, transcrição, correção e notas; nunca
áudio) e sobrevive a fechar o app. Cada mudança regrava o arquivo inteiro: primeiro num
arquivo temporário, depois trocando de nome, para nunca deixar o histórico pela metade.
Excluir uma sessão tira ela do arquivo na mesma hora.
"""

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.repositorio.memoria import RepositorioMemoria
from app.schemas.llm import Fala
from app.schemas.sessao import Avaliacao, Consentimento, Sessao

logger = logging.getLogger(__name__)

VERSAO_ARQUIVO = 1

EM_ANDAMENTO = {"processando_audio", "corrigindo", "gerando_sugestoes"}
"""Etapas em segundo plano: se o app fechou no meio, a sessão volta como erro para tentar de novo."""

MENSAGEM_INTERROMPIDA = "O app foi fechado antes de terminar esta etapa. Tente de novo."


class ErroArquivoHistorico(RuntimeError):
    """O arquivo do histórico existe mas não dá para ler. Nada é apagado nem sobrescrito."""


class RepositorioArquivo(RepositorioMemoria):
    def __init__(self, caminho: Path) -> None:
        super().__init__()
        self._caminho = caminho
        self._trava_arquivo = threading.Lock()
        self._ilegiveis: list[Any] = []
        """Sessões que não passaram na validação (de outra versão do app): voltam ao arquivo como estavam."""
        self._carregar()

    def _carregar(self) -> None:
        if not self._caminho.exists():
            return
        try:
            dados = json.loads(self._caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError) as erro:
            raise ErroArquivoHistorico(
                f"Não deu para ler o histórico em {self._caminho} ({type(erro).__name__}). "
                "Nada foi apagado. Renomeie o arquivo para começar um histórico novo."
            ) from None
        if not isinstance(dados, dict) or not isinstance(dados.get("sessoes"), list):
            raise ErroArquivoHistorico(
                f"O histórico em {self._caminho} não está no formato esperado. "
                "Nada foi apagado. Renomeie o arquivo para começar um histórico novo."
            )

        interrompidas = 0
        for bruta in dados["sessoes"]:
            try:
                sessao = Sessao.model_validate(bruta)
            except ValidationError:
                self._ilegiveis.append(bruta)
                continue
            if sessao.status in EM_ANDAMENTO:
                sessao = sessao.model_copy(
                    update={"status": "erro", "progresso": 0, "mensagem_erro": MENSAGEM_INTERROMPIDA}
                )
                interrompidas += 1
            self._sessoes[sessao.id] = sessao
        fila = dados.get("fila_queixas")
        if isinstance(fila, dict):
            self.fila_queixas.update(fila)
        # Só contagens no log, nunca conteúdo.
        logger.info(
            "histórico carregado: %d sessões, %d interrompidas, %d ilegíveis",
            len(self._sessoes),
            interrompidas,
            len(self._ilegiveis),
        )
        if interrompidas:
            self._gravar()

    def _gravar(self) -> None:
        with self._trava_arquivo:
            with self._trava:
                dados = {
                    "versao": VERSAO_ARQUIVO,
                    "sessoes": [s.model_dump(mode="json") for s in self._sessoes.values()] + self._ilegiveis,
                    "fila_queixas": json.loads(json.dumps(self.fila_queixas)),
                }
            self._caminho.parent.mkdir(parents=True, exist_ok=True)
            descritor, temporario = tempfile.mkstemp(dir=self._caminho.parent, prefix=".historico-", suffix=".tmp")
            try:
                with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
                    json.dump(dados, arquivo, ensure_ascii=False)
                    arquivo.flush()
                    os.fsync(arquivo.fileno())
                os.replace(temporario, self._caminho)
            except BaseException:
                Path(temporario).unlink(missing_ok=True)
                raise

    def criar_sessao(self, sessao: Sessao) -> None:
        super().criar_sessao(sessao)
        self._gravar()

    def atualizar_sessao(self, sessao_id: str, **campos: Any) -> None:
        super().atualizar_sessao(sessao_id, **campos)
        self._gravar()

    def salvar_transcricao(self, sessao_id: str, falas: list[Fala], editada: bool) -> None:
        super().salvar_transcricao(sessao_id, falas, editada)
        self._gravar()

    def salvar_avaliacoes(self, sessao_id: str, avaliacoes: list[Avaliacao]) -> None:
        super().salvar_avaliacoes(sessao_id, avaliacoes)
        self._gravar()

    def adicionar_consentimento(self, consentimento: Consentimento) -> None:
        super().adicionar_consentimento(consentimento)
        self._gravar()

    def apagar_sessao(self, sessao_id: str) -> None:
        super().apagar_sessao(sessao_id)
        self._gravar()

    def registrar_queixa_outra(self, descricao: str) -> None:
        super().registrar_queixa_outra(descricao)
        self._gravar()
