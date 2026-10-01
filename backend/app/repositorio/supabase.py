"""Repositório no Supabase (Postgres), com a service key. Só roda no servidor.

Tabelas e colunas usadas (a migração fica em supabase/migrations/):
- usuarios: id
- sessoes: id, dono_id, criada_em, status, progresso, mensagem_erro, origem_caso, cartao_id,
  queixa_detectada, queixa_trecho, queixas_confirmadas, descricao_outra,
  checklists_usados (jsonb), anamnese (jsonb), hipoteses_aluno (jsonb), notas (jsonb),
  sugestoes (jsonb)
- consentimentos: id, sessao_id, papel, nome_informado, versao_termo, aceito_em
- transcricoes: sessao_id (único), falas (jsonb), editada
- avaliacoes: sessao_id, ordem, item_id, checklist_id, checklist_versao, secao, texto, status,
  trecho, mensagem, peso, conta_na_nota, contestacao (jsonb)
- fila_queixas: descricao_normalizada (único), exemplo, frequencia, status
"""

from typing import Any

from pydantic import BaseModel

from app.repositorio.base import Repositorio, conferir_campos
from app.schemas.llm import Fala
from app.schemas.sessao import Avaliacao, Consentimento, Sessao
from app.texto import normalizar

CAMPOS_LISTA = ("queixa_detectada", "queixas_confirmadas", "checklists_usados", "hipoteses_aluno")


def _json(valor: Any) -> Any:
    """Modelos Pydantic (e listas deles) para tipos que o PostgREST aceita."""
    if isinstance(valor, BaseModel):
        return valor.model_dump(mode="json")
    if isinstance(valor, list):
        return [_json(v) for v in valor]
    return valor


class RepositorioSupabase(Repositorio):
    def __init__(self, url: str, chave_servico: str) -> None:
        from supabase import create_client

        self._db = create_client(url, chave_servico)

    def _tabela(self, nome: str) -> Any:
        return self._db.table(nome)

    # ---------- sessões ----------

    def criar_sessao(self, sessao: Sessao) -> None:
        self._tabela("usuarios").upsert({"id": sessao.dono_id}, ignore_duplicates=True).execute()
        linha = sessao.model_dump(mode="json", exclude={"consentimentos", "falas", "transcricao_editada", "avaliacoes"})
        self._tabela("sessoes").insert(linha).execute()

    def _montar(self, linha: dict[str, Any], completa: bool) -> Sessao:
        dados = dict(linha)
        for campo in CAMPOS_LISTA:
            dados[campo] = dados.get(campo) or []
        if completa:
            sessao_id = linha["id"]
            dados["consentimentos"] = (
                self._tabela("consentimentos").select("*").eq("sessao_id", sessao_id).order("aceito_em").execute().data
            )
            transcricao = (
                self._tabela("transcricoes").select("falas, editada").eq("sessao_id", sessao_id).limit(1).execute().data
            )
            if transcricao:
                dados["falas"] = transcricao[0].get("falas") or []
                dados["transcricao_editada"] = bool(transcricao[0].get("editada"))
            avaliacoes = self._tabela("avaliacoes").select("*").eq("sessao_id", sessao_id).order("ordem").execute().data
            dados["avaliacoes"] = [
                {campo: valor for campo, valor in a.items() if campo in Avaliacao.model_fields} for a in avaliacoes
            ]
        return Sessao.model_validate(dados)

    def obter_sessao(self, sessao_id: str) -> Sessao | None:
        linhas = self._tabela("sessoes").select("*").eq("id", sessao_id).limit(1).execute().data
        return self._montar(linhas[0], completa=True) if linhas else None

    def listar_sessoes(self, dono_id: str) -> list[Sessao]:
        linhas = self._tabela("sessoes").select("*").eq("dono_id", dono_id).order("criada_em", desc=True).execute().data
        return [self._montar(linha, completa=False) for linha in linhas]

    def atualizar_sessao(self, sessao_id: str, **campos: Any) -> None:
        conferir_campos(campos)
        if campos:
            linha = {campo: _json(valor) for campo, valor in campos.items()}
            self._tabela("sessoes").update(linha).eq("id", sessao_id).execute()

    def salvar_transcricao(self, sessao_id: str, falas: list[Fala], editada: bool) -> None:
        self._tabela("transcricoes").upsert(
            {"sessao_id": sessao_id, "falas": _json(falas), "editada": editada}, on_conflict="sessao_id"
        ).execute()

    def _versoes_checklists(self, sessao_id: str) -> dict[str, int]:
        linhas = self._tabela("sessoes").select("checklists_usados").eq("id", sessao_id).limit(1).execute().data
        usados = (linhas[0].get("checklists_usados") if linhas else None) or []
        return {c["id"]: c["versao"] for c in usados}

    def salvar_avaliacoes(self, sessao_id: str, avaliacoes: list[Avaliacao]) -> None:
        versoes = self._versoes_checklists(sessao_id) if avaliacoes else {}
        self._tabela("avaliacoes").delete().eq("sessao_id", sessao_id).execute()
        if avaliacoes:
            linhas = [
                {
                    "sessao_id": sessao_id,
                    "ordem": ordem,
                    "checklist_versao": versoes.get(a.checklist_id),
                    **a.model_dump(mode="json"),
                }
                for ordem, a in enumerate(avaliacoes)
            ]
            self._tabela("avaliacoes").insert(linhas).execute()

    def adicionar_consentimento(self, consentimento: Consentimento) -> None:
        self._tabela("consentimentos").insert(consentimento.model_dump(mode="json")).execute()

    def apagar_sessao(self, sessao_id: str) -> None:
        # Apaga os filhos antes, para não depender de ON DELETE CASCADE.
        for tabela in ("avaliacoes", "transcricoes", "consentimentos"):
            self._tabela(tabela).delete().eq("sessao_id", sessao_id).execute()
        self._tabela("sessoes").delete().eq("id", sessao_id).execute()

    # ---------- fila de queixas ----------

    def registrar_queixa_outra(self, descricao: str) -> None:
        chave = normalizar(descricao)
        if not chave:
            return
        tabela = self._tabela("fila_queixas")
        existentes = tabela.select("frequencia").eq("descricao_normalizada", chave).limit(1).execute().data
        if existentes:
            frequencia = int(existentes[0].get("frequencia") or 0) + 1
            tabela.update({"frequencia": frequencia}).eq("descricao_normalizada", chave).execute()
        else:
            tabela.insert(
                {"descricao_normalizada": chave, "exemplo": descricao.strip()[:200], "frequencia": 1}
            ).execute()
