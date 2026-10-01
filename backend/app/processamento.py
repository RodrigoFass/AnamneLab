"""Etapas em segundo plano (BackgroundTasks do FastAPI), com status e progresso.

áudio -> transcrever e apagar -> rotular falas -> detectar queixa -> aguardando_queixa
queixa confirmada -> anamnese + correção -> aguardando_hipoteses
hipóteses do aluno -> sugestões -> concluida

Qualquer falha vira status "erro" com mensagem em PT-BR para o aluno. No log vão só o
id da sessão, a etapa e o tipo do erro: nada de transcrição, áudio ou dado pessoal.
"""

import logging
from pathlib import Path

from app.llm import ErroLLM
from app.llm.base import MENSAGEM_PADRAO
from app.pipeline.anamnese import montar_anamnese
from app.pipeline.comum import ErroPipeline
from app.pipeline.corrigir import corrigir
from app.pipeline.queixa import detectar_queixa
from app.pipeline.rotular_falas import rotular_falas, rotular_simples
from app.pipeline.sugestoes import gerar_sugestoes
from app.pipeline.transcrever import ErroTranscricao, apagar_audio, montar_dica, transcrever_e_apagar
from app.servicos import Servicos

logger = logging.getLogger(__name__)

MENSAGENS_ETAPA = {
    "audio": "Não deu para ouvir a gravação. Grave de novo num lugar mais calmo.",
    "correcao": "Não deu para montar a correção agora. Tente de novo em alguns minutos.",
    "sugestoes": "Não deu para gerar as sugestões agora. Tente de novo em alguns minutos.",
}


class Processador:
    def __init__(self, servicos: Servicos) -> None:
        self._s = servicos

    @property
    def _repo(self):
        return self._s.repositorio

    def _falhou(self, sessao_id: str, etapa: str, erro: Exception) -> None:
        if isinstance(erro, (ErroLLM, ErroTranscricao, ErroPipeline)) and erro.mensagem != MENSAGEM_PADRAO:
            mensagem = erro.mensagem  # mensagem específica (recusa, conversa longa, gravação longa...)
        else:
            mensagem = MENSAGENS_ETAPA[etapa]
        logger.warning("etapa falhou (sessao=%s, etapa=%s, erro=%s)", sessao_id, etapa, type(erro).__name__)
        try:
            self._repo.atualizar_sessao(sessao_id, status="erro", progresso=0, mensagem_erro=mensagem)
        except Exception as erro_banco:
            logger.error(
                "não deu para registrar o erro (sessao=%s, etapa=%s, erro=%s)",
                sessao_id,
                etapa,
                type(erro_banco).__name__,
            )

    # ---------- etapa 1: áudio ----------

    def processar_audio(self, sessao_id: str, caminho: Path) -> None:
        try:
            conteudo = self._s.conteudo
            self._repo.atualizar_sessao(sessao_id, progresso=15)
            texto = transcrever_e_apagar(caminho, self._s.transcritor, dica=montar_dica(conteudo.queixas))
            if self._repo.obter_sessao(sessao_id) is None:
                return  # o aluno apagou a sessão no meio do caminho
            self._repo.atualizar_sessao(sessao_id, progresso=55)

            try:
                falas = rotular_falas(texto, self._s.llm)
            except ErroLLM:
                # O áudio já foi apagado: separa as falas sem IA e o aluno corrige.
                logger.warning("rotulagem sem IA (sessao=%s)", sessao_id)
                falas = rotular_simples(texto)
                if not falas:
                    raise
            self._repo.salvar_transcricao(sessao_id, falas, editada=False)
            self._repo.atualizar_sessao(sessao_id, progresso=80)

            try:
                detectada = detectar_queixa(falas, conteudo.queixas, self._s.llm)
                campos = {
                    "queixa_detectada": detectada.queixas,
                    "queixa_trecho": detectada.trecho or None,
                    "descricao_outra": detectada.descricao_outra,
                }
            except ErroLLM:
                # Sem sugestão de queixa: o aluno escolhe na lista.
                logger.warning("queixa sem sugestão (sessao=%s)", sessao_id)
                campos = {"queixa_detectada": [], "queixa_trecho": None, "descricao_outra": None}
            self._repo.atualizar_sessao(
                sessao_id, status="aguardando_queixa", progresso=100, mensagem_erro=None, **campos
            )
        except Exception as erro:
            self._falhou(sessao_id, "audio", erro)
        finally:
            apagar_audio(caminho)  # já foi apagado na transcrição; aqui cobre falha antes dela

    # ---------- etapa 2: anamnese e correção ----------

    def processar_queixa(self, sessao_id: str) -> None:
        try:
            sessao = self._repo.obter_sessao(sessao_id)
            if sessao is None:
                return
            conteudo = self._s.conteudo
            anamnese = montar_anamnese(sessao.falas, self._s.llm)
            self._repo.atualizar_sessao(sessao_id, anamnese=anamnese, progresso=40)
            resultado = corrigir(
                sessao.falas,
                sessao.queixas_confirmadas,
                conteudo,
                self._s.llm,
                contar_rascunho=self._s.settings.contar_rascunho,
            )
            # Id e versão dos checklists primeiro: cada avaliação salva aponta para eles (regra 4).
            self._repo.atualizar_sessao(sessao_id, checklists_usados=resultado.checklists_usados)
            self._repo.salvar_avaliacoes(sessao_id, resultado.avaliacoes)
            self._repo.atualizar_sessao(
                sessao_id,
                notas=resultado.notas,
                status="aguardando_hipoteses",
                progresso=100,
                mensagem_erro=None,
            )
        except Exception as erro:
            self._falhou(sessao_id, "correcao", erro)

    # ---------- etapa 3: sugestões ----------

    def processar_hipoteses(self, sessao_id: str) -> None:
        try:
            sessao = self._repo.obter_sessao(sessao_id)
            if sessao is None:
                return
            self._repo.atualizar_sessao(sessao_id, progresso=30)
            sugestoes = gerar_sugestoes(
                sessao.falas,
                sessao.queixas_confirmadas,
                sessao.descricao_outra,
                sessao.hipoteses_aluno,
                sessao.avaliacoes,
                self._s.conteudo,
                self._s.llm,
            )
            self._repo.atualizar_sessao(
                sessao_id, sugestoes=sugestoes, status="concluida", progresso=100, mensagem_erro=None
            )
        except Exception as erro:
            self._falhou(sessao_id, "sugestoes", erro)
