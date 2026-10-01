"""Repositório em memória, para desenvolvimento e testes. Some quando o processo para."""

import threading
from typing import Any

from app.repositorio.base import Repositorio, conferir_campos
from app.schemas.llm import Fala
from app.schemas.sessao import Avaliacao, Consentimento, Sessao
from app.texto import normalizar


class RepositorioMemoria(Repositorio):
    def __init__(self) -> None:
        self._sessoes: dict[str, Sessao] = {}
        self.fila_queixas: dict[str, dict[str, Any]] = {}
        self._trava = threading.Lock()

    def criar_sessao(self, sessao: Sessao) -> None:
        with self._trava:
            self._sessoes[sessao.id] = sessao.model_copy(deep=True)

    def obter_sessao(self, sessao_id: str) -> Sessao | None:
        with self._trava:
            sessao = self._sessoes.get(sessao_id)
            return sessao.model_copy(deep=True) if sessao else None

    def listar_sessoes(self, dono_id: str) -> list[Sessao]:
        with self._trava:
            sessoes = [s.model_copy(deep=True) for s in self._sessoes.values() if s.dono_id == dono_id]
        return sorted(sessoes, key=lambda s: s.criada_em, reverse=True)

    def _alterar(self, sessao_id: str, **campos: Any) -> None:
        with self._trava:
            sessao = self._sessoes.get(sessao_id)
            if sessao is not None:
                self._sessoes[sessao_id] = sessao.model_copy(update=campos, deep=True)

    def atualizar_sessao(self, sessao_id: str, **campos: Any) -> None:
        conferir_campos(campos)
        self._alterar(sessao_id, **campos)

    def salvar_transcricao(self, sessao_id: str, falas: list[Fala], editada: bool) -> None:
        self._alterar(sessao_id, falas=list(falas), transcricao_editada=editada)

    def salvar_avaliacoes(self, sessao_id: str, avaliacoes: list[Avaliacao]) -> None:
        self._alterar(sessao_id, avaliacoes=list(avaliacoes))

    def adicionar_consentimento(self, consentimento: Consentimento) -> None:
        with self._trava:
            sessao = self._sessoes.get(consentimento.sessao_id)
            if sessao is not None:
                self._sessoes[sessao.id] = sessao.model_copy(
                    update={"consentimentos": [*sessao.consentimentos, consentimento]}, deep=True
                )

    def apagar_sessao(self, sessao_id: str) -> None:
        with self._trava:
            self._sessoes.pop(sessao_id, None)

    def registrar_queixa_outra(self, descricao: str) -> None:
        chave = normalizar(descricao)
        if not chave:
            return
        with self._trava:
            registro = self.fila_queixas.setdefault(
                chave, {"descricao_normalizada": chave, "frequencia": 0, "status": "pendente"}
            )
            registro["frequencia"] += 1
