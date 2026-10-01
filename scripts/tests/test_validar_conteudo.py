"""Testes do validador de conteúdo.

Cada teste copia o content/ real para uma pasta temporária, estraga um arquivo e
confere que o validador recusa com uma mensagem que aponta o arquivo.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
CONTEUDO = SCRIPTS.parent / "content"
SCRIPT = SCRIPTS / "validar_conteudo.py"

_spec = importlib.util.spec_from_file_location("validar_conteudo", SCRIPT)
validar_conteudo = importlib.util.module_from_spec(_spec)
sys.modules["validar_conteudo"] = validar_conteudo
_spec.loader.exec_module(validar_conteudo)


@pytest.fixture
def pasta(tmp_path: Path) -> Path:
    destino = tmp_path / "content"
    shutil.copytree(CONTEUDO, destino)
    return destino


def ler(pasta: Path, relativo: str) -> dict:
    return json.loads((pasta / relativo).read_text(encoding="utf-8"))


def gravar(pasta: Path, relativo: str, dados: dict) -> None:
    (pasta / relativo).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def primeiro_item(checklist: dict) -> dict:
    return checklist["secoes"][0]["itens"][0]


def problemas(pasta: Path) -> list[str]:
    return validar_conteudo.validar(pasta).problemas


def tem(lista: list[str], arquivo: str, trecho: str) -> bool:
    return any(p.startswith(arquivo + ":") and trecho in p for p in lista)


# --- conteúdo real -----------------------------------------------------------


def test_conteudo_real_passa():
    res = validar_conteudo.validar(CONTEUDO)
    assert res.problemas == []
    assert res.checklists == 2
    assert res.queixas == 10
    assert res.cartoes == 30
    assert res.arquivos == 5


def test_linha_de_comando_conteudo_real():
    saida = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False
    )
    assert saida.returncode == 0, saida.stdout
    assert "tudo certo" in saida.stdout


def test_linha_de_comando_falha_com_codigo_1(pasta: Path):
    termo = ler(pasta, "termo-gravacao.json")
    del termo["texto"]
    gravar(pasta, "termo-gravacao.json", termo)
    saida = subprocess.run(
        [sys.executable, str(SCRIPT), str(pasta)], capture_output=True, text=True, check=False
    )
    assert saida.returncode == 1
    assert "termo-gravacao.json:" in saida.stdout
    assert "texto" in saida.stdout


def test_item_compartilhado_conta_uma_vez():
    res = validar_conteudo.validar(CONTEUDO)
    geral = ler(CONTEUDO, "checklists/geral.json")
    dor = ler(CONTEUDO, "checklists/dor-toracica.json")
    ids = [i["id"] for c in (geral, dor) for s in c["secoes"] for i in s["itens"]]
    assert "tabagismo" in ids
    assert res.itens == len(set(ids))


# --- casos errados -----------------------------------------------------------


def test_item_sem_fonte(pasta: Path):
    dados = ler(pasta, "checklists/geral.json")
    del primeiro_item(dados)["fonte"]
    gravar(pasta, "checklists/geral.json", dados)
    lista = problemas(pasta)
    assert tem(lista, "checklists/geral.json", "fonte")


def test_aprovado_sem_assinatura(pasta: Path):
    dados = ler(pasta, "checklists/dor-toracica.json")
    dados["status"] = "aprovado"
    dados["validado_por"] = None
    dados["validado_em"] = None
    gravar(pasta, "checklists/dor-toracica.json", dados)
    lista = problemas(pasta)
    assert tem(lista, "checklists/dor-toracica.json", "validado_por")
    assert tem(lista, "checklists/dor-toracica.json", "validado_em")


def test_aprovado_com_assinatura_passa(pasta: Path):
    dados = ler(pasta, "checklists/dor-toracica.json")
    dados["status"] = "aprovado"
    dados["validado_por"] = "Prof. Fulano de Tal"
    dados["validado_em"] = "2026-10-01"
    gravar(pasta, "checklists/dor-toracica.json", dados)
    assert problemas(pasta) == []


def test_data_de_assinatura_invalida(pasta: Path):
    dados = ler(pasta, "checklists/dor-toracica.json")
    dados["status"] = "aprovado"
    dados["validado_por"] = "Prof. Fulano de Tal"
    dados["validado_em"] = "01/10/2026"
    gravar(pasta, "checklists/dor-toracica.json", dados)
    assert tem(problemas(pasta), "checklists/dor-toracica.json", "validado_em")


def test_id_duplicado_com_texto_diferente(pasta: Path):
    dados = ler(pasta, "checklists/dor-toracica.json")
    for secao in dados["secoes"]:
        for item in secao["itens"]:
            if item["id"] == "tabagismo":
                item["texto"] = "Fuma?"
    gravar(pasta, "checklists/dor-toracica.json", dados)
    lista = [p for p in problemas(pasta) if "'tabagismo'" in p]
    assert len(lista) == 1
    assert "geral.json" in lista[0] and "dor-toracica.json" in lista[0]


def test_id_repetido_dentro_do_checklist(pasta: Path):
    dados = ler(pasta, "checklists/geral.json")
    dados["secoes"][0]["itens"].append(dict(primeiro_item(dados)))
    gravar(pasta, "checklists/geral.json", dados)
    assert tem(problemas(pasta), "checklists/geral.json", "repetido")


def test_queixa_inexistente_no_checklist(pasta: Path):
    dados = ler(pasta, "checklists/dor-toracica.json")
    dados["queixa"] = "dor-no-cotovelo"
    gravar(pasta, "checklists/dor-toracica.json", dados)
    lista = problemas(pasta)
    assert tem(lista, "checklists/dor-toracica.json", "dor-no-cotovelo")


def test_queixa_inexistente_no_cartao(pasta: Path):
    dados = ler(pasta, "cartoes/cartoes.json")
    dados["cartoes"][0]["queixa"] = "dor-no-cotovelo"
    gravar(pasta, "cartoes/cartoes.json", dados)
    assert tem(problemas(pasta), "cartoes/cartoes.json", "dor-no-cotovelo")


def test_checklist_referenciado_inexistente(pasta: Path):
    dados = ler(pasta, "queixas.json")
    dados["queixas"][1]["checklist"] = "dispneia"
    gravar(pasta, "queixas.json", dados)
    assert tem(problemas(pasta), "queixas.json", "'dispneia'")


def test_livro_sem_pagina(pasta: Path):
    dados = ler(pasta, "checklists/geral.json")
    primeiro_item(dados)["fonte"] = {"tipo": "livro", "referencia": "Porto, Semiologia médica"}
    gravar(pasta, "checklists/geral.json", dados)
    assert tem(problemas(pasta), "checklists/geral.json", "pagina")


def test_id_diferente_do_nome_do_arquivo(pasta: Path):
    dados = ler(pasta, "checklists/geral.json")
    dados["id"] = "geral-2"
    gravar(pasta, "checklists/geral.json", dados)
    assert tem(problemas(pasta), "checklists/geral.json", "nome do arquivo")


def test_tipo_geral_com_queixa(pasta: Path):
    dados = ler(pasta, "checklists/geral.json")
    dados["queixa"] = "dor-toracica"
    gravar(pasta, "checklists/geral.json", dados)
    assert tem(problemas(pasta), "checklists/geral.json", "geral")


def test_cartao_repetido(pasta: Path):
    dados = ler(pasta, "cartoes/cartoes.json")
    dados["cartoes"].append(dict(dados["cartoes"][0]))
    gravar(pasta, "cartoes/cartoes.json", dados)
    assert tem(problemas(pasta), "cartoes/cartoes.json", "repetido")


def test_json_quebrado(pasta: Path):
    (pasta / "queixas.json").write_text("{ isto não é json", encoding="utf-8")
    assert tem(problemas(pasta), "queixas.json", "JSON inválido")
