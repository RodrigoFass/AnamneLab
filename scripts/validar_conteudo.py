#!/usr/bin/env python3
"""Valida todo o conteúdo do AnamneLab (queixas, checklists, cartões e termo).

Uso:
    python scripts/validar_conteudo.py [pasta_de_conteudo]

Sem argumento, valida a pasta content/ ao lado de scripts/. Imprime uma linha por
problema, com o arquivo, e sai com código 1. Sem problemas, imprime um resumo e
sai com código 0. Dependência: jsonschema.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

PASTA_PADRAO = Path(__file__).resolve().parent.parent / "content"

ARQ_QUEIXAS = "queixas.json"
ARQ_TERMO = "termo-gravacao.json"
DIR_CHECKLISTS = "checklists"
DIR_CARTOES = "cartoes"

SCHEMAS = {
    "queixas": "queixas.schema.json",
    "checklist": "checklist.schema.json",
    "cartao": "cartao.schema.json",
    "termo": "termo.schema.json",
}


@dataclass
class Resultado:
    problemas: list[str] = field(default_factory=list)
    arquivos: int = 0
    queixas: int = 0
    checklists: int = 0
    itens: int = 0
    cartoes: int = 0

    def erro(self, arquivo: str, mensagem: str) -> None:
        self.problemas.append(f"{arquivo}: {mensagem}")


# ---------------------------------------------------------------------------
# Mensagens do jsonschema em PT-BR


def _caminho(erro: ValidationError) -> str:
    partes = [str(p) for p in erro.absolute_path]
    return "/".join(partes) if partes else "(raiz)"


def _mensagem_schema(erro: ValidationError) -> str:
    v = erro.validator
    valor = erro.instance
    esperado = erro.validator_value
    if v == "required":
        faltando = [c for c in esperado if isinstance(valor, dict) and c not in valor]
        campos = ", ".join(f"'{c}'" for c in faltando) or str(esperado)
        texto = f"falta o campo obrigatório {campos}"
    elif v == "additionalProperties":
        permitidos = set(erro.schema.get("properties", {}))
        extras = sorted(k for k in valor if k not in permitidos) if isinstance(valor, dict) else []
        texto = "campo não permitido: " + ", ".join(f"'{c}'" for c in extras)
    elif v == "type":
        tipos = esperado if isinstance(esperado, list) else [esperado]
        texto = f"tipo errado, esperado {' ou '.join(tipos)}, veio {json.dumps(valor, ensure_ascii=False)}"
    elif v == "enum":
        opcoes = ", ".join(json.dumps(o, ensure_ascii=False) for o in esperado)
        texto = f"valor {json.dumps(valor, ensure_ascii=False)} fora das opções ({opcoes})"
    elif v == "const":
        texto = f"valor deveria ser {json.dumps(esperado, ensure_ascii=False)}"
    elif v == "pattern":
        texto = f"'{valor}' não segue o padrão {esperado} (use kebab-case: letras minúsculas, números e hífen)"
    elif v == "minLength":
        texto = "texto vazio" if esperado == 1 else f"texto com menos de {esperado} caracteres"
    elif v == "maxLength":
        texto = f"texto com mais de {esperado} caracteres"
    elif v == "minItems":
        texto = f"lista com menos de {esperado} item(ns)"
    elif v == "maxItems":
        texto = f"lista com mais de {esperado} item(ns)"
    elif v == "minimum":
        texto = f"valor {valor} menor que o mínimo {esperado}"
    elif v == "maximum":
        texto = f"valor {valor} maior que o máximo {esperado}"
    elif v == "format":
        texto = f"{json.dumps(valor, ensure_ascii=False)} não é um valor válido no formato '{esperado}'"
    elif v == "not":
        texto = f"valor {json.dumps(valor, ensure_ascii=False)} não é permitido"
    else:
        texto = f"valor inválido (regra '{v}')"
    return f"{_caminho(erro)}: {texto}"


# ---------------------------------------------------------------------------
# Leitura


def _carregar_json(caminho: Path, nome: str, res: Resultado) -> Any | None:
    if not caminho.is_file():
        res.erro(nome, "arquivo não encontrado")
        return None
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        res.erro(nome, f"JSON inválido na linha {e.lineno}, coluna {e.colno}: {e.msg}")
    except UnicodeDecodeError:
        res.erro(nome, "o arquivo precisa estar em UTF-8")
    return None


def _validadores(pasta: Path, res: Resultado) -> dict[str, Draft202012Validator]:
    validadores = {}
    for chave, arquivo in SCHEMAS.items():
        nome = f"schema/{arquivo}"
        schema = _carregar_json(pasta / "schema" / arquivo, nome, res)
        if schema is None:
            continue
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as e:  # SchemaError
            res.erro(nome, f"schema inválido: {getattr(e, 'message', e)}")
            continue
        validadores[chave] = Draft202012Validator(
            schema, format_checker=Draft202012Validator.FORMAT_CHECKER
        )
    return validadores


def _validar_schema(dados: Any, validador: Draft202012Validator | None, nome: str, res: Resultado) -> bool:
    if validador is None:
        return False
    erros = sorted(validador.iter_errors(dados), key=lambda e: [str(p) for p in e.absolute_path])
    for erro in erros:
        res.erro(nome, _mensagem_schema(erro))
    return not erros


def _relativo(caminho: Path, pasta: Path) -> str:
    return caminho.relative_to(pasta).as_posix()


def _e_lista(valor: Any) -> list:
    return valor if isinstance(valor, list) else []


def _e_dict(valor: Any) -> dict:
    return valor if isinstance(valor, dict) else {}


# ---------------------------------------------------------------------------
# Validação


def validar(pasta: Path) -> Resultado:
    pasta = Path(pasta)
    res = Resultado()
    if not pasta.is_dir():
        res.erro(str(pasta), "pasta de conteúdo não encontrada")
        return res

    validadores = _validadores(pasta, res)

    # Queixas
    queixas_dados = _carregar_json(pasta / ARQ_QUEIXAS, ARQ_QUEIXAS, res)
    queixas: dict[str, dict] = {}
    if queixas_dados is not None:
        res.arquivos += 1
        _validar_schema(queixas_dados, validadores.get("queixas"), ARQ_QUEIXAS, res)
        sinonimos_vistos: dict[str, str] = {}
        for q in _e_lista(_e_dict(queixas_dados).get("queixas")):
            q = _e_dict(q)
            qid = q.get("id")
            if not isinstance(qid, str):
                continue
            if qid in queixas:
                res.erro(ARQ_QUEIXAS, f"queixa '{qid}' repetida")
            queixas[qid] = q
            termos = [q.get("nome")] + _e_lista(q.get("sinonimos"))
            for termo in termos:
                if not isinstance(termo, str):
                    continue
                chave = termo.strip().lower()
                dono = sinonimos_vistos.get(chave)
                if dono is not None and dono != qid:
                    res.erro(ARQ_QUEIXAS, f"o termo '{termo}' aparece em '{dono}' e em '{qid}'")
                sinonimos_vistos.setdefault(chave, qid)
        res.queixas = len(queixas)

    # Checklists
    dir_checklists = pasta / DIR_CHECKLISTS
    arquivos_checklist = sorted(dir_checklists.glob("*.json")) if dir_checklists.is_dir() else []
    if not arquivos_checklist:
        res.erro(DIR_CHECKLISTS, "nenhum checklist encontrado")
    checklists: dict[str, dict] = {}
    # id do item -> (arquivo, texto, faltou, peso)
    itens_globais: dict[str, tuple[str, Any, Any, Any]] = {}

    for caminho in arquivos_checklist:
        nome = _relativo(caminho, pasta)
        dados = _carregar_json(caminho, nome, res)
        if dados is None:
            continue
        res.arquivos += 1
        res.checklists += 1
        _validar_schema(dados, validadores.get("checklist"), nome, res)
        dados = _e_dict(dados)
        cid = dados.get("id")
        if cid != caminho.stem:
            res.erro(nome, f"o id '{cid}' precisa ser igual ao nome do arquivo ('{caminho.stem}')")
        if isinstance(cid, str):
            checklists[cid] = dados

        tipo = dados.get("tipo")
        queixa = dados.get("queixa")
        if tipo == "geral" and queixa is not None:
            res.erro(nome, "checklist do tipo 'geral' não pode ter queixa")
        if tipo == "queixa":
            if not isinstance(queixa, str) or not queixa:
                res.erro(nome, "checklist do tipo 'queixa' precisa dizer qual é a queixa")
            elif queixas_dados is not None and queixa not in queixas:
                res.erro(nome, f"a queixa '{queixa}' não existe em {ARQ_QUEIXAS}")

        if dados.get("status") == "aprovado":
            if not dados.get("validado_por"):
                res.erro(nome, "checklist aprovado precisa de 'validado_por' (quem assinou)")
            if not dados.get("validado_em"):
                res.erro(nome, "checklist aprovado precisa de 'validado_em' (data da assinatura)")

        ids_secao: set[str] = set()
        ids_item: set[str] = set()
        for secao in _e_lista(dados.get("secoes")):
            secao = _e_dict(secao)
            sid = secao.get("id")
            if isinstance(sid, str):
                if sid in ids_secao:
                    res.erro(nome, f"seção '{sid}' repetida")
                ids_secao.add(sid)
            for item in _e_lista(secao.get("itens")):
                item = _e_dict(item)
                iid = item.get("id")
                if not isinstance(iid, str):
                    continue
                if iid in ids_item:
                    res.erro(nome, f"item '{iid}' repetido dentro do checklist")
                    continue
                ids_item.add(iid)
                _checar_fonte(item, iid, nome, res)
                assinatura = (item.get("texto"), item.get("faltou"), item.get("peso"))
                anterior = itens_globais.get(iid)
                if anterior is None:
                    itens_globais[iid] = (nome, *assinatura)
                elif anterior[1:] != assinatura:
                    res.erro(
                        nome,
                        f"item '{iid}' também está em {anterior[0]} com texto, faltou ou peso "
                        "diferentes; o mesmo id precisa ser o mesmo item (ou use outro id)",
                    )
    res.itens = len(itens_globais)

    if checklists and "geral" not in checklists:
        res.erro(DIR_CHECKLISTS, "falta o checklist 'geral' (geral.json)")

    # Queixas apontam para checklists que existem e que são da mesma queixa
    for qid, q in queixas.items():
        ref = q.get("checklist")
        if ref is None:
            continue
        alvo = checklists.get(ref)
        if alvo is None:
            res.erro(ARQ_QUEIXAS, f"a queixa '{qid}' aponta para o checklist '{ref}', que não existe")
        elif alvo.get("queixa") != qid:
            res.erro(ARQ_QUEIXAS, f"a queixa '{qid}' aponta para o checklist '{ref}', que é de outra queixa")

    # Cartões
    dir_cartoes = pasta / DIR_CARTOES
    arquivos_cartao = sorted(dir_cartoes.glob("*.json")) if dir_cartoes.is_dir() else []
    if not arquivos_cartao:
        res.erro(DIR_CARTOES, "nenhum arquivo de cartões encontrado")
    ids_cartao: dict[str, str] = {}
    for caminho in arquivos_cartao:
        nome = _relativo(caminho, pasta)
        dados = _carregar_json(caminho, nome, res)
        if dados is None:
            continue
        res.arquivos += 1
        _validar_schema(dados, validadores.get("cartao"), nome, res)
        for cartao in _e_lista(_e_dict(dados).get("cartoes")):
            cartao = _e_dict(cartao)
            cid = cartao.get("id")
            if isinstance(cid, str):
                if cid in ids_cartao:
                    res.erro(nome, f"cartão '{cid}' repetido (já está em {ids_cartao[cid]})")
                ids_cartao[cid] = nome
                res.cartoes += 1
            queixa = cartao.get("queixa")
            if queixas_dados is not None and isinstance(queixa, str) and queixa not in queixas:
                res.erro(nome, f"cartão '{cid}': a queixa '{queixa}' não existe em {ARQ_QUEIXAS}")

    # Termo de gravação
    termo = _carregar_json(pasta / ARQ_TERMO, ARQ_TERMO, res)
    if termo is not None:
        res.arquivos += 1
        _validar_schema(termo, validadores.get("termo"), ARQ_TERMO, res)

    return res


def _checar_fonte(item: dict, iid: str, nome: str, res: Resultado) -> None:
    fonte = item.get("fonte")
    if not isinstance(fonte, dict):
        res.erro(nome, f"item '{iid}' sem fonte")
        return
    if fonte.get("tipo") == "livro" and not fonte.get("pagina"):
        res.erro(nome, f"item '{iid}': fonte do tipo livro precisa da página")
    url = fonte.get("url")
    if isinstance(url, str) and not url.startswith(("https://", "http://")):
        res.erro(nome, f"item '{iid}': a url da fonte precisa começar com https://")


def resumo(res: Resultado) -> str:
    return (
        f"{res.arquivos} arquivos, {res.queixas} queixas, {res.checklists} checklists, "
        f"{res.itens} itens, {res.cartoes} cartões, tudo certo"
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        print("uso: python scripts/validar_conteudo.py [pasta_de_conteudo]", file=sys.stderr)
        return 2
    pasta = Path(args[0]) if args else PASTA_PADRAO
    res = validar(pasta)
    if res.problemas:
        for linha in res.problemas:
            print(linha)
        print(f"{len(res.problemas)} problema(s) encontrado(s).")
        return 1
    print(resumo(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
