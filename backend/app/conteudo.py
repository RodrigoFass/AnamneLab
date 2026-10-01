"""Carrega e valida o conteúdo de content/ (queixas, checklists, cartões e termo).

O conteúdo é lido uma vez por pasta e fica em cache na memória. Conteúdo inválido
levanta ErroConteudo com o arquivo e o motivo, para quem mantém o app corrigir.
"""

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.schemas.conteudo import BibliotecaCartoes, BibliotecaQueixas, Checklist, Queixa
from app.schemas.sessao import Termo

QUEIXA_OUTRA = "outra"

ARQUIVO_QUEIXAS = "queixas.json"
ARQUIVO_TERMO = "termo-gravacao.json"
PASTA_CHECKLISTS = "checklists"
ARQUIVO_CARTOES = Path("cartoes") / "cartoes.json"


class ErroConteudo(Exception):
    """Conteúdo ausente ou inválido em content/."""


@dataclass(frozen=True)
class Conteudo:
    queixas: BibliotecaQueixas
    checklists: dict[str, Checklist]
    cartoes: BibliotecaCartoes
    termo: Termo
    _queixas_por_id: dict[str, Queixa] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_queixas_por_id", {q.id: q for q in self.queixas.queixas})

    @property
    def ids_queixas(self) -> set[str]:
        return set(self._queixas_por_id)

    def queixa(self, queixa_id: str) -> Queixa | None:
        return self._queixas_por_id.get(queixa_id)

    @property
    def checklist_geral(self) -> Checklist:
        for checklist in self.checklists.values():
            if checklist.tipo == "geral":
                return checklist
        raise ErroConteudo("Não há checklist geral em content/checklists/.")

    def checklist_da_queixa(self, queixa_id: str) -> Checklist | None:
        queixa = self.queixa(queixa_id)
        if queixa is None or queixa.checklist is None:
            return None
        return self.checklists.get(queixa.checklist)

    def tipos_checklists(self) -> dict[str, str]:
        return {c.id: c.tipo for c in self.checklists.values()}


def _ler_json(caminho: Path) -> object:
    if not caminho.is_file():
        raise ErroConteudo(f"Arquivo de conteúdo não encontrado: {caminho}")
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        raise ErroConteudo(f"{caminho} não é um JSON válido (linha {erro.lineno}, coluna {erro.colno}).") from None


def _validar[M: BaseModel](modelo: type[M], dados: object, caminho: Path) -> M:
    try:
        return modelo.model_validate(dados)
    except ValidationError as erro:
        problemas = "; ".join(f"{'.'.join(str(p) for p in e['loc']) or '(raiz)'}: {e['msg']}" for e in erro.errors())
        raise ErroConteudo(f"{caminho} não segue o formato esperado: {problemas}") from None


def carregar_conteudo(pasta: Path) -> Conteudo:
    """Lê content/ do disco, valida e confere as referências entre arquivos."""
    pasta = Path(pasta)
    if not pasta.is_dir():
        raise ErroConteudo(f"Pasta de conteúdo não encontrada: {pasta}")

    caminho_queixas = pasta / ARQUIVO_QUEIXAS
    queixas = _validar(BibliotecaQueixas, _ler_json(caminho_queixas), caminho_queixas)

    pasta_checklists = pasta / PASTA_CHECKLISTS
    arquivos = sorted(pasta_checklists.glob("*.json")) if pasta_checklists.is_dir() else []
    if not arquivos:
        raise ErroConteudo(f"Nenhum checklist encontrado em {pasta_checklists}")
    checklists: dict[str, Checklist] = {}
    for arquivo in arquivos:
        checklist = _validar(Checklist, _ler_json(arquivo), arquivo)
        if checklist.id != arquivo.stem:
            raise ErroConteudo(f"{arquivo}: o id '{checklist.id}' precisa ser igual ao nome do arquivo.")
        ids_itens = [item.id for item in checklist.itens]
        repetidos = sorted({i for i in ids_itens if ids_itens.count(i) > 1})
        if repetidos:
            raise ErroConteudo(f"{arquivo}: itens com id repetido: {', '.join(repetidos)}")
        checklists[checklist.id] = checklist

    caminho_cartoes = pasta / ARQUIVO_CARTOES
    cartoes = _validar(BibliotecaCartoes, _ler_json(caminho_cartoes), caminho_cartoes)

    caminho_termo = pasta / ARQUIVO_TERMO
    dados_termo = _ler_json(caminho_termo)
    if isinstance(dados_termo, dict) and isinstance(dados_termo.get("versao"), int):
        dados_termo = {**dados_termo, "versao": str(dados_termo["versao"])}
    termo = _validar(Termo, dados_termo, caminho_termo)

    _conferir_referencias(queixas, checklists, cartoes)
    return Conteudo(queixas=queixas, checklists=checklists, cartoes=cartoes, termo=termo)


def _conferir_referencias(
    queixas: BibliotecaQueixas, checklists: dict[str, Checklist], cartoes: BibliotecaCartoes
) -> None:
    ids_queixas = [q.id for q in queixas.queixas]
    if len(set(ids_queixas)) != len(ids_queixas):
        raise ErroConteudo("queixas.json tem queixas com id repetido.")
    if QUEIXA_OUTRA in ids_queixas:
        raise ErroConteudo("queixas.json não pode ter a queixa 'outra': ela é reservada.")

    gerais = [c.id for c in checklists.values() if c.tipo == "geral"]
    if len(gerais) != 1:
        raise ErroConteudo(f"Precisa haver exatamente um checklist geral; há {len(gerais)}.")

    for checklist in checklists.values():
        if checklist.tipo == "queixa" and checklist.queixa not in ids_queixas:
            raise ErroConteudo(
                f"Checklist '{checklist.id}' aponta para a queixa '{checklist.queixa}', que não está em queixas.json."
            )
    for queixa in queixas.queixas:
        if queixa.checklist is not None and queixa.checklist not in checklists:
            raise ErroConteudo(f"A queixa '{queixa.id}' aponta para o checklist '{queixa.checklist}', que não existe.")
    for cartao in cartoes.cartoes:
        if cartao.queixa not in ids_queixas:
            raise ErroConteudo(
                f"O cartão '{cartao.id}' aponta para a queixa '{cartao.queixa}', que não está em queixas.json."
            )


_cache: dict[Path, Conteudo] = {}
_trava = threading.Lock()


def obter_conteudo(pasta: Path) -> Conteudo:
    """Conteúdo da pasta, carregado uma vez e guardado em memória."""
    chave = Path(pasta).resolve()
    with _trava:
        if chave not in _cache:
            _cache[chave] = carregar_conteudo(chave)
        return _cache[chave]


def limpar_cache() -> None:
    with _trava:
        _cache.clear()
