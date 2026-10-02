"""Confere se a IA de correção configurada no backend/.env responde de verdade.

Uso, dentro de backend/:
    .venv/bin/python -m app.testar_ia             (no Windows: .venv\\Scripts\\python -m app.testar_ia)
    .venv/bin/python -m app.testar_ia --modelos   lista os modelos do Gemini que a chave acessa

Passa a transcrição de exemplo (uma consulta simulada, sem dados de ninguém) pelas etapas
de IA do app: separar as falas, detectar a queixa, montar a anamnese, corrigir e sugerir
hipóteses. Mostra o tempo de cada etapa e qual modelo respondeu. Não grava nada.
"""

import argparse
import sys
import time
from collections.abc import Callable
from typing import Any

from app.config import Settings, obter_settings
from app.conteudo import carregar_conteudo
from app.llm import ClienteLLM, ErroLLM, obter_cliente_llm
from app.pipeline.anamnese import montar_anamnese
from app.pipeline.corrigir import corrigir
from app.pipeline.queixa import detectar_queixa
from app.pipeline.rotular_falas import rotular_falas
from app.pipeline.sugestoes import gerar_sugestoes
from app.pipeline.transcrever import ARQUIVO_EXEMPLO

DICAS = {
    429: "A cota grátis deste modelo acabou por agora (ou o modelo não tem cota grátis). "
    "Espere um pouco ou ponha outro modelo em GEMINI_MODELOS.",
    404: "Esse modelo não existe para a sua chave. Rode com --modelos e ajuste GEMINI_MODELOS.",
    403: "A chave não tem permissão. Confira se ela foi criada no Google AI Studio.",
}


def _explicar_erro(llm: ClienteLLM) -> None:
    erro = getattr(llm, "ultimo_erro", None)
    if erro is None:
        return
    print(f"    modelo: {erro.modelo} | HTTP {erro.status_http} | {erro.codigo}")
    print(f"    resposta do Google: {erro.mensagem[:300]}")
    if erro.codigo and "API_KEY_INVALID" in erro.codigo:
        print("    Dica: a chave está errada. Copie de novo no Google AI Studio para GEMINI_API_KEY.")
    elif erro.status_http in DICAS:
        print(f"    Dica: {DICAS[erro.status_http]}")


def _etapa(nome: str, llm: ClienteLLM, funcao: Callable[[], Any], resumo: Callable[[Any], str]) -> Any:
    inicio = time.monotonic()
    try:
        resultado = funcao()
    except ErroLLM as erro:
        print(f"  [falhou] {nome} ({time.monotonic() - inicio:.1f} s): {erro.mensagem}")
        _explicar_erro(llm)
        sys.exit(1)
    modelo = getattr(llm, "ultimo_modelo", None)
    sufixo = f", {modelo}" if modelo else ""
    print(f"  [ok] {nome} ({time.monotonic() - inicio:.1f} s{sufixo}): {resumo(resultado)}")
    return resultado


def testar(settings: Settings) -> None:
    print(f"IA de correção: {settings.llm_provedor}")
    if settings.llm_provedor == "gemini":
        print(f"Modelos, em ordem: {', '.join(settings.lista_modelos_gemini) or '(nenhum)'}")
        if not settings.gemini_api_key:
            sys.exit("Falta GEMINI_API_KEY no backend/.env.")
    elif settings.llm_provedor == "anthropic":
        print(f"Modelo: {settings.llm_modelo} ({settings.llm_esforco})")
    else:
        sys.exit("LLM_PROVEDOR=falso: não há IA para testar. Ponha LLM_PROVEDOR=gemini no backend/.env.")

    conteudo = carregar_conteudo(settings.pasta_conteudo)
    llm = obter_cliente_llm(settings)
    texto = ARQUIVO_EXEMPLO.read_text(encoding="utf-8")
    print("\nTranscrição de exemplo:")

    falas = _etapa("Separar as falas", llm, lambda: rotular_falas(texto, llm), lambda f: f"{len(f)} falas")
    detectada = _etapa(
        "Detectar a queixa",
        llm,
        lambda: detectar_queixa(falas, conteudo.queixas, llm),
        lambda d: ", ".join(d.queixas) or "nenhuma",
    )
    queixas = detectada.queixas or ["outra"]
    _etapa("Montar a anamnese", llm, lambda: montar_anamnese(falas, llm), lambda _: "pronta")
    resultado = _etapa(
        "Corrigir pelos checklists",
        llm,
        lambda: corrigir(
            falas,
            queixas,
            conteudo,
            llm,
            contar_rascunho=settings.contar_rascunho,
            itens_por_pedido=settings.correcao_itens_por_pedido,
        ),
        lambda r: (
            f"{sum(a.status == 'feito' for a in r.avaliacoes)} de {len(r.avaliacoes)} itens feitos, "
            f"nota geral {r.notas.geral}, queixa {r.notas.queixa}"
        ),
    )
    _etapa(
        "Sugerir hipóteses",
        llm,
        lambda: gerar_sugestoes(
            falas, queixas, detectada.descricao_outra, ["Hipótese de teste"], resultado.avaliacoes, conteudo, llm
        ),
        lambda s: f"{len(s.hipoteses)} hipóteses",
    )
    print("\nTudo certo: a correção por IA está funcionando.")


def mostrar_modelos(settings: Settings) -> None:
    from app.llm.gemini import listar_modelos

    try:
        nomes = listar_modelos(settings)
    except ErroLLM as erro:
        sys.exit(erro.mensagem)
    print("Modelos do Gemini que a sua chave acessa (para GEMINI_MODELOS):")
    for nome in nomes:
        print(f"  {nome}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modelos", action="store_true", help="lista os modelos do Gemini que a chave acessa")
    args = parser.parse_args()
    settings = obter_settings()
    if args.modelos:
        mostrar_modelos(settings)
    else:
        testar(settings)


if __name__ == "__main__":
    main()
