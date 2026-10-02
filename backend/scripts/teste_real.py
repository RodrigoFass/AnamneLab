"""Roda uma gravação de ponta a ponta pelo backend, com a configuração do .env.

Serve para o teste com IA de verdade (TRANSCRICAO=api ou local, LLM_PROVEDOR=anthropic):
faz o mesmo caminho do app (sessão, dois aceites, áudio, queixa, hipóteses), mede o tempo
de cada etapa e salva a sessão final em JSON para conferir a correção item a item.

Uso, dentro de backend/:
    uv run python scripts/teste_real.py gravacao.m4a
    uv run python scripts/teste_real.py gravacao.m4a --hipoteses "Síndrome coronariana aguda" "Pericardite"
    uv run python scripts/teste_real.py gravacao.m4a --queixa dor-toracica --saida resultado.json

O áudio passa pelo mesmo descarte do app: uma cópia vai para o backend e é apagada depois
da transcrição; o arquivo original não é tocado.
"""

import argparse
import json
import mimetypes
import sys
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.config import obter_settings
from app.main import criar_app

ESPERA_MAXIMA_S = 600


def esperar(cliente: TestClient, sessao_id: str, alvo: str) -> tuple[dict[str, Any], float]:
    inicio = time.monotonic()
    while True:
        sessao = cliente.get(f"/api/sessoes/{sessao_id}").json()
        if sessao["status"] == alvo:
            return sessao, time.monotonic() - inicio
        if sessao["status"] == "erro":
            sys.exit(f"A sessão parou com erro: {sessao.get('mensagem_erro')}")
        if time.monotonic() - inicio > ESPERA_MAXIMA_S:
            sys.exit(f"Passou de {ESPERA_MAXIMA_S} s esperando '{alvo}' (status: {sessao['status']}).")
        time.sleep(0.5)


def exigir(resposta: Any, etapa: str) -> dict[str, Any]:
    if resposta.status_code >= 400:
        sys.exit(f"{etapa} falhou ({resposta.status_code}): {resposta.text}")
    return resposta.json()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("audio", type=Path, help="gravação (webm, ogg, m4a, mp3 ou wav)")
    parser.add_argument("--queixa", nargs="+", help="ids da queixa a confirmar; sem isto, usa a detectada")
    parser.add_argument("--hipoteses", nargs="+", default=["Hipótese de teste"], help="hipóteses do aluno")
    parser.add_argument("--saida", type=Path, default=Path("resultado-teste-real.json"))
    args = parser.parse_args()

    if not args.audio.is_file():
        sys.exit(f"Arquivo não encontrado: {args.audio}")

    settings = obter_settings()
    print(f"Transcrição: {settings.transcricao} | LLM: {settings.llm_provedor} ({settings.llm_modelo}, {settings.llm_esforco})")
    if settings.transcricao == "falso" or settings.llm_provedor == "falso":
        print("Aviso: alguma parte está em modo falso; o resultado não usa IA de verdade.")

    tempos: dict[str, float] = {}
    with TestClient(criar_app(settings)) as cliente:
        termo = exigir(cliente.get("/api/termo"), "Ler o termo")
        sessao = exigir(cliente.post("/api/sessoes", json={"origem_caso": "inventado"}), "Abrir a sessão")
        sessao_id = sessao["id"]
        for papel in ("medico", "paciente"):
            corpo = {"papel": papel, "nome_informado": f"Teste {papel}", "versao_termo": termo["versao"], "aceito": True}
            exigir(cliente.post(f"/api/sessoes/{sessao_id}/consentimentos", json=corpo), f"Aceite ({papel})")

        tipo = mimetypes.guess_type(args.audio.name)[0] or "application/octet-stream"
        arquivos = {"audio": (args.audio.name, args.audio.read_bytes(), tipo)}
        exigir(cliente.post(f"/api/sessoes/{sessao_id}/audio", files=arquivos), "Enviar o áudio")
        sessao, tempos["transcrever e separar falas"] = esperar(cliente, sessao_id, "aguardando_queixa")

        print(f"\nFalas: {len(sessao['falas'])}")
        for fala in sessao["falas"][:6]:
            print(f"  {fala['papel']}: {fala['texto'][:100]}")
        print(f"Queixa detectada: {sessao['queixa_detectada']} (trecho: {sessao['queixa_trecho']!r})")

        queixas = args.queixa or sessao["queixa_detectada"] or ["outra"]
        corpo = {"queixas": queixas}
        if queixas == ["outra"]:
            corpo["descricao_outra"] = "teste"
        exigir(cliente.post(f"/api/sessoes/{sessao_id}/queixa", json=corpo), "Confirmar a queixa")
        sessao, tempos["anamnese e correção"] = esperar(cliente, sessao_id, "aguardando_hipoteses")

        corpo = {"hipoteses": args.hipoteses}
        exigir(cliente.post(f"/api/sessoes/{sessao_id}/hipoteses", json=corpo), "Enviar as hipóteses")
        sessao, tempos["sugestões"] = esperar(cliente, sessao_id, "concluida")

    avaliacoes = sessao["avaliacoes"]
    feitos = [a for a in avaliacoes if a["status"] == "feito"]
    print(f"\nQueixas confirmadas: {sessao['queixas_confirmadas']}")
    print(f"Itens: {len(feitos)} feitos de {len(avaliacoes)} (todo 'feito' tem trecho conferido)")
    print(f"Notas: {sessao['notas']}")
    print("\nTempo por etapa:")
    for etapa, segundos in tempos.items():
        print(f"  {etapa}: {segundos:.1f} s")
    args.saida.write_text(json.dumps(sessao, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSessão completa salva em {args.saida}")


if __name__ == "__main__":
    main()
