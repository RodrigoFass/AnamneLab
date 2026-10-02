"""Fluxo completo pela API: LLM falso, transcrição falsa, banco em memória e em arquivo."""

import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth import Usuario, usuario_atual
from app.llm.base import ErroLLM
from app.llm.falso import ClienteFalso
from app.main import criar_app
from app.pipeline.transcrever import Transcritor, TranscritorFalso
from app.repositorio.arquivo import RepositorioArquivo
from app.repositorio.memoria import RepositorioMemoria

AUDIO = ("gravacao.webm", b"\x1a\x45\xdf\xa3" + b"0" * 2048, "audio/webm;codecs=opus")


@pytest.fixture(params=["memoria", "arquivo"])
def repositorio(request, tmp_path) -> RepositorioMemoria:
    if request.param == "arquivo":
        return RepositorioArquivo(tmp_path / "dados" / "historico.json")
    return RepositorioMemoria()


@pytest.fixture
def app(settings, repositorio):
    return criar_app(settings, repositorio=repositorio)


@pytest.fixture
def cliente(app):
    with TestClient(app) as cliente:
        yield cliente


def esperar(cliente: TestClient, sessao_id: str, status: str, limite_s: float = 5) -> dict[str, Any]:
    fim = time.monotonic() + limite_s
    while True:
        sessao = cliente.get(f"/api/sessoes/{sessao_id}").json()
        if sessao["status"] == status or time.monotonic() > fim:
            assert sessao["status"] == status, sessao.get("mensagem_erro")
            return sessao
        time.sleep(0.05)


def nova_sessao(cliente: TestClient) -> str:
    resposta = cliente.post("/api/sessoes", json={"origem_caso": "inventado"})
    assert resposta.status_code == 201
    assert resposta.json()["status"] == "criada"
    return resposta.json()["id"]


def consentir(cliente: TestClient, sessao_id: str, papel: str, versao: str = "1"):
    return cliente.post(
        f"/api/sessoes/{sessao_id}/consentimentos",
        json={"papel": papel, "nome_informado": f"Colega {papel}", "versao_termo": versao, "aceito": True},
    )


def gravada(cliente: TestClient) -> str:
    """Sessão com os dois aceites e o áudio processado (aguardando_queixa)."""
    sessao_id = nova_sessao(cliente)
    assert consentir(cliente, sessao_id, "medico").status_code == 201
    assert consentir(cliente, sessao_id, "paciente").status_code == 201
    assert cliente.post(f"/api/sessoes/{sessao_id}/audio", files={"audio": AUDIO}).status_code == 200
    esperar(cliente, sessao_id, "aguardando_queixa")
    return sessao_id


def arquivos_de_audio(settings) -> list[Path]:
    pasta = settings.pasta_audio_temp
    return list(pasta.iterdir()) if pasta.exists() else []


# ---------- rotas simples ----------


def test_rotas_de_conteudo(cliente):
    assert cliente.get("/api/saude").json() == {"ok": True, "modo_demonstracao": True}
    assert [q["id"] for q in cliente.get("/api/queixas").json()] == ["dor-toracica", "cefaleia"]
    assert cliente.get("/api/termo").json()["versao"] == "1"
    assert cliente.get("/api/cartoes/sortear").json()["id"] == "dor-toracica-teste-1"
    assert cliente.get("/api/cartoes/sortear?queixa=dor-toracica").status_code == 200
    resposta = cliente.get("/api/cartoes/sortear?queixa=cefaleia")
    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "Ainda não há cartões para essa queixa."


def test_sessao_com_cartao(cliente):
    resposta = cliente.post("/api/sessoes", json={"origem_caso": "cartao", "cartao_id": "dor-toracica-teste-1"})
    assert resposta.status_code == 201
    assert resposta.json()["cartao_id"] == "dor-toracica-teste-1"
    assert cliente.post("/api/sessoes", json={"origem_caso": "cartao"}).status_code == 422
    assert cliente.post("/api/sessoes", json={"origem_caso": "cartao", "cartao_id": "nao-existe"}).status_code == 422


def test_erro_de_validacao_vem_em_portugues(cliente):
    resposta = cliente.post("/api/sessoes", json={"origem_caso": "sonho"})
    assert resposta.status_code == 422
    assert isinstance(resposta.json()["detail"], str)
    assert "origem_caso" in resposta.json()["detail"]


# ---------- fluxo completo ----------


def test_fluxo_completo(cliente, settings, repositorio):
    sessao_id = nova_sessao(cliente)

    # Sem os dois aceites, o áudio é recusado e nada fica salvo.
    resposta = cliente.post(f"/api/sessoes/{sessao_id}/audio", files={"audio": AUDIO})
    assert resposta.status_code == 409
    assert "aceitar o termo" in resposta.json()["detail"]
    assert consentir(cliente, sessao_id, "medico").status_code == 201
    assert cliente.post(f"/api/sessoes/{sessao_id}/audio", files={"audio": AUDIO}).status_code == 409
    assert consentir(cliente, sessao_id, "paciente", versao="0").status_code == 409  # termo antigo
    consentimento = consentir(cliente, sessao_id, "paciente")
    assert consentimento.status_code == 201
    assert consentimento.json()["papel"] == "paciente"
    assert consentimento.json()["versao_termo"] == "1"
    assert arquivos_de_audio(settings) == []

    # Formato não aceito.
    resposta = cliente.post(f"/api/sessoes/{sessao_id}/audio", files={"audio": ("nota.txt", b"texto", "text/plain")})
    assert resposta.status_code == 415

    # Áudio aceito: processa em segundo plano e o arquivo some.
    resposta = cliente.post(f"/api/sessoes/{sessao_id}/audio", files={"audio": AUDIO})
    assert resposta.status_code == 200
    sessao = esperar(cliente, sessao_id, "aguardando_queixa")
    assert arquivos_de_audio(settings) == []
    assert len(sessao["consentimentos"]) == 2
    assert len(sessao["falas"]) > 40
    assert sessao["falas"][0]["papel"] == "entrevistador"
    assert sessao["queixa_detectada"][0] == "dor-toracica"
    assert sessao["queixa_trecho"]
    assert sessao["transcricao_editada"] is False

    # Segundo áudio na mesma sessão não entra.
    assert cliente.post(f"/api/sessoes/{sessao_id}/audio", files={"audio": AUDIO}).status_code == 409

    # Corrige uma fala: acrescenta a pergunta sobre alergias.
    falas = sessao["falas"]
    falas.insert(2, {"papel": "entrevistador", "texto": "O senhor tem alguma alergia a remédio?"})
    falas.insert(3, {"papel": "paciente", "texto": "Não que eu saiba."})
    # E o paciente conta que quase desmaiou, sem o entrevistador ter perguntado do desmaio.
    falas.append({"papel": "entrevistador", "texto": "Quer contar mais alguma coisa?"})
    falas.append({"papel": "paciente", "texto": "Ah, e na hora da dor eu achei que ia desmaiar."})
    resposta = cliente.put(f"/api/sessoes/{sessao_id}/transcricao", json={"falas": falas})
    assert resposta.status_code == 200
    assert resposta.json()["transcricao_editada"] is True
    assert resposta.json()["falas"][2]["texto"] == "O senhor tem alguma alergia a remédio?"
    assert cliente.put(f"/api/sessoes/{sessao_id}/transcricao", json={"falas": []}).status_code == 422

    # Queixa fora da lista é recusada; confirma dor torácica.
    assert cliente.post(f"/api/sessoes/{sessao_id}/queixa", json={"queixas": ["inventada"]}).status_code == 422
    resposta = cliente.post(f"/api/sessoes/{sessao_id}/queixa", json={"queixas": ["dor-toracica"]})
    assert resposta.status_code == 200
    sessao = esperar(cliente, sessao_id, "aguardando_hipoteses")

    # A correção existe, mas não aparece antes das hipóteses.
    assert repositorio.obter_sessao(sessao_id).avaliacoes
    assert sessao["avaliacoes"] == []
    assert sessao["notas"] is None
    assert sessao["sugestoes"] is None
    assert sessao["anamnese"]["queixa_principal"]
    assert [(c["id"], c["versao"], c["status"]) for c in sessao["checklists_usados"]] == [
        ("geral", 3, "rascunho"),
        ("dor-toracica", 2, "rascunho"),
    ]
    assert cliente.get("/api/sessoes").json()[0]["notas"] is None
    assert cliente.put(f"/api/sessoes/{sessao_id}/transcricao", json={"falas": falas}).status_code == 409
    contestacao = {"item_id": "sincope", "motivo": "Perguntei.", "trecho": "Quantos anos o senhor tem?"}
    assert cliente.post(f"/api/sessoes/{sessao_id}/contestacoes", json=contestacao).status_code == 409

    # Hipóteses do aluno liberam a correção e as sugestões.
    assert cliente.post(f"/api/sessoes/{sessao_id}/hipoteses", json={"hipoteses": ["  "]}).status_code == 422
    resposta = cliente.post(f"/api/sessoes/{sessao_id}/hipoteses", json={"hipoteses": ["Síndrome coronariana aguda"]})
    assert resposta.status_code == 200
    sessao = esperar(cliente, sessao_id, "concluida")
    assert sessao["hipoteses_aluno"] == ["Síndrome coronariana aguda"]
    avaliacoes = {a["item_id"]: a for a in sessao["avaliacoes"]}
    assert len(avaliacoes) == 7  # tabagismo está nos dois checklists e conta uma vez
    assert avaliacoes["idade"]["status"] == "feito"
    assert avaliacoes["idade"]["trecho"] == "Quantos anos o senhor tem?"
    assert avaliacoes["alergias"]["status"] == "feito"  # veio da transcrição editada
    assert avaliacoes["sincope"]["status"] == "faltou"
    assert avaliacoes["sincope"]["mensagem"] == "Faltou perguntar se desmaiou ou quase desmaiou."
    assert sessao["sexo_paciente"] == "masculino"  # detectado ("o senhor") e mantido na confirmação
    assert sessao["notas"] == {"geral": 100, "queixa": 71, "provisoria": True}
    # Dor torácica tem checklist: sem perguntas sugeridas fora da nota.
    assert sessao["sugestoes"]["perguntas_sugeridas"] == []
    assert sessao["sugestoes"]["hipoteses"]
    assert cliente.get("/api/sessoes").json()[0]["notas"]["queixa"] == 71

    # Contestação com trecho que não está na conversa: pendente, nota igual.
    resposta = cliente.post(
        f"/api/sessoes/{sessao_id}/contestacoes",
        json={"item_id": "sincope", "motivo": "Acho que perguntei.", "trecho": "Já desmaiou alguma vez?"},
    )
    assert resposta.status_code == 200
    sincope = next(a for a in resposta.json()["avaliacoes"] if a["item_id"] == "sincope")
    assert sincope["contestacao"]["resultado"] == "pendente_professor"
    assert resposta.json()["notas"]["queixa"] == 71

    # Fala que existe, mas sem relação com o item: continua pendente, nota igual.
    resposta = cliente.post(f"/api/sessoes/{sessao_id}/contestacoes", json=contestacao)
    assert resposta.status_code == 200
    sincope = next(a for a in resposta.json()["avaliacoes"] if a["item_id"] == "sincope")
    assert sincope["status"] == "faltou"
    assert sincope["contestacao"]["resultado"] == "pendente_professor"
    assert resposta.json()["notas"]["queixa"] == 71

    # Fala só do paciente: o LLM nem é chamado, continua pendente, nota igual.
    contestacao = {
        "item_id": "sincope",
        "motivo": "O paciente falou do desmaio.",
        "trecho": "Ah, e na hora da dor eu achei que ia desmaiar.",
    }
    resposta = cliente.post(f"/api/sessoes/{sessao_id}/contestacoes", json=contestacao)
    assert resposta.status_code == 200
    sincope = next(a for a in resposta.json()["avaliacoes"] if a["item_id"] == "sincope")
    assert sincope["contestacao"]["resultado"] == "pendente_professor"
    assert resposta.json()["notas"]["queixa"] == 71

    # Pergunta do entrevistador e resposta que mostram o item: procedente, nota recalculada.
    contestacao["trecho"] = "Quer contar mais alguma coisa? Ah, e na hora da dor eu achei que ia desmaiar."
    resposta = cliente.post(f"/api/sessoes/{sessao_id}/contestacoes", json=contestacao)
    assert resposta.status_code == 200
    sincope = next(a for a in resposta.json()["avaliacoes"] if a["item_id"] == "sincope")
    assert sincope["status"] == "feito"
    assert sincope["contestacao"]["resultado"] == "procedente"
    assert resposta.json()["notas"]["queixa"] == 100
    resposta = cliente.post(f"/api/sessoes/{sessao_id}/contestacoes", json=contestacao)
    assert resposta.status_code == 409  # já está feito

    # Apagar some com tudo.
    assert cliente.delete(f"/api/sessoes/{sessao_id}").status_code == 204
    assert cliente.get(f"/api/sessoes/{sessao_id}").status_code == 404
    assert repositorio.obter_sessao(sessao_id) is None
    assert cliente.get("/api/sessoes").json() == []


def test_outro_usuario_recebe_404(app, cliente):
    sessao_id = gravada(cliente)
    app.dependency_overrides[usuario_atual] = lambda: Usuario(id="outro-aluno")
    try:
        assert cliente.get(f"/api/sessoes/{sessao_id}").status_code == 404
        assert cliente.get("/api/sessoes").json() == []
        assert (
            cliente.put(
                f"/api/sessoes/{sessao_id}/transcricao", json={"falas": [{"papel": "paciente", "texto": "x"}]}
            ).status_code
            == 404
        )
        assert cliente.post(f"/api/sessoes/{sessao_id}/queixa", json={"queixas": ["dor-toracica"]}).status_code == 404
        assert consentir(cliente, sessao_id, "medico").status_code == 404
        assert cliente.delete(f"/api/sessoes/{sessao_id}").status_code == 404
    finally:
        app.dependency_overrides.clear()
    assert cliente.get(f"/api/sessoes/{sessao_id}").status_code == 200


def test_queixa_outra_vai_para_a_fila_e_usa_so_o_geral(cliente, repositorio):
    sessao_id = gravada(cliente)
    assert cliente.post(f"/api/sessoes/{sessao_id}/queixa", json={"queixas": ["outra"]}).status_code == 422
    resposta = cliente.post(
        f"/api/sessoes/{sessao_id}/queixa", json={"queixas": ["outra"], "descricao_outra": "Dor no calcanhar!"}
    )
    assert resposta.status_code == 200
    esperar(cliente, sessao_id, "aguardando_hipoteses")
    assert repositorio.fila_queixas["dor no calcanhar"]["frequencia"] == 1

    outra_id = gravada(cliente)
    cliente.post(f"/api/sessoes/{outra_id}/queixa", json={"queixas": ["outra"], "descricao_outra": "dor no CALCANHAR"})
    assert repositorio.fila_queixas["dor no calcanhar"]["frequencia"] == 2

    cliente.post(f"/api/sessoes/{sessao_id}/hipoteses", json={"hipoteses": ["Fascite plantar"]})
    sessao = esperar(cliente, sessao_id, "concluida")
    assert {a["checklist_id"] for a in sessao["avaliacoes"]} == {"geral"}
    assert sessao["notas"]["queixa"] is None
    assert sessao["sugestoes"]["perguntas_sugeridas"]  # queixa sem critério: perguntas fora da nota
    assert [c["id"] for c in sessao["checklists_usados"]] == ["geral"]


def test_audio_grande_demais(app, settings):
    settings.tamanho_maximo_mb = 1
    with TestClient(app) as cliente:
        sessao_id = nova_sessao(cliente)
        consentir(cliente, sessao_id, "medico")
        consentir(cliente, sessao_id, "paciente")
        grande = ("gravacao.webm", b"0" * (1024 * 1024 + 10), "audio/webm")
        resposta = cliente.post(f"/api/sessoes/{sessao_id}/audio", files={"audio": grande})
        assert resposta.status_code == 413
        assert "1 MB" in resposta.json()["detail"]
        assert arquivos_de_audio(settings) == []
        assert cliente.get(f"/api/sessoes/{sessao_id}").json()["status"] == "criada"


# ---------- falhas viram status "erro" com mensagem de preceptor ----------


class TranscritorQueFalha(Transcritor):
    def transcrever(self, caminho: Path, *, dica: str = "") -> str:
        raise RuntimeError("falha interna com dado sensível que não pode aparecer")


class FalsoQueFalhaUmaVez(ClienteFalso):
    def __init__(self, tarefa: str) -> None:
        self.tarefa = tarefa
        self.falhou = False

    def _gerar_json(self, *, tarefa, **kwargs) -> str:
        if tarefa == self.tarefa and not self.falhou:
            self.falhou = True
            raise ErroLLM()
        return super()._gerar_json(tarefa=tarefa, **kwargs)


def test_falha_na_transcricao_apaga_o_audio_e_explica(settings, repositorio):
    app = criar_app(settings, repositorio=repositorio, transcritor=TranscritorQueFalha())
    with TestClient(app) as cliente:
        sessao_id = nova_sessao(cliente)
        consentir(cliente, sessao_id, "medico")
        consentir(cliente, sessao_id, "paciente")
        cliente.post(f"/api/sessoes/{sessao_id}/audio", files={"audio": AUDIO})
        sessao = esperar(cliente, sessao_id, "erro")
        assert sessao["mensagem_erro"] == "Não deu para ouvir a gravação. Grave de novo num lugar mais calmo."
        assert "sensível" not in sessao["mensagem_erro"]
        assert arquivos_de_audio(settings) == []
        # Dá para gravar de novo na mesma sessão.
        app.state.servicos.transcritor = TranscritorFalso()
        assert cliente.post(f"/api/sessoes/{sessao_id}/audio", files={"audio": AUDIO}).status_code == 200
        esperar(cliente, sessao_id, "aguardando_queixa")


def test_falha_na_correcao_vira_erro_e_permite_nova_tentativa(settings, repositorio):
    app = criar_app(settings, repositorio=repositorio, llm=FalsoQueFalhaUmaVez("corrigir"))
    with TestClient(app) as cliente:
        sessao_id = gravada(cliente)
        cliente.post(f"/api/sessoes/{sessao_id}/queixa", json={"queixas": ["dor-toracica"]})
        sessao = esperar(cliente, sessao_id, "erro")
        assert sessao["mensagem_erro"] == "Não deu para montar a correção agora. Tente de novo em alguns minutos."
        cliente.post(f"/api/sessoes/{sessao_id}/queixa", json={"queixas": ["dor-toracica"]})
        esperar(cliente, sessao_id, "aguardando_hipoteses")


def test_falha_ao_rotular_usa_o_plano_b_e_nao_perde_a_gravacao(settings, repositorio):
    app = criar_app(settings, repositorio=repositorio, llm=FalsoQueFalhaUmaVez("rotular"))
    with TestClient(app) as cliente:
        sessao_id = gravada(cliente)
        sessao = cliente.get(f"/api/sessoes/{sessao_id}").json()
        assert sessao["falas"]
        assert any(f["papel"] == "entrevistador" for f in sessao["falas"])


def test_falha_nas_sugestoes_mostra_a_correcao_e_permite_nova_tentativa(settings, repositorio):
    app = criar_app(settings, repositorio=repositorio, llm=FalsoQueFalhaUmaVez("sugestoes"))
    with TestClient(app) as cliente:
        sessao_id = gravada(cliente)
        cliente.post(f"/api/sessoes/{sessao_id}/queixa", json={"queixas": ["dor-toracica"]})
        esperar(cliente, sessao_id, "aguardando_hipoteses")
        cliente.post(f"/api/sessoes/{sessao_id}/hipoteses", json={"hipoteses": ["Angina"]})
        sessao = esperar(cliente, sessao_id, "erro")
        assert sessao["mensagem_erro"] == "Não deu para gerar as sugestões agora. Tente de novo em alguns minutos."
        assert sessao["avaliacoes"]  # o aluno já escreveu as hipóteses: a correção aparece
        cliente.post(f"/api/sessoes/{sessao_id}/hipoteses", json={"hipoteses": ["Outra coisa"]})
        sessao = esperar(cliente, sessao_id, "concluida")
        assert sessao["hipoteses_aluno"] == ["Angina"]
        assert sessao["sugestoes"]


def test_sobras_de_audio_sao_apagadas_na_subida(settings, repositorio):
    pasta = settings.pasta_audio_temp
    pasta.mkdir(parents=True)
    sobra = pasta / "anamnelab-sobra.webm"
    sobra.write_bytes(b"audio velho")
    alheio = pasta / "outro-arquivo.txt"
    alheio.write_text("não é nosso")
    with TestClient(criar_app(settings, repositorio=repositorio)):
        pass
    assert not sobra.exists()
    assert alheio.exists()


def test_outra_nao_se_mistura_com_queixa_da_lista(cliente, repositorio):
    sessao_id = gravada(cliente)
    resposta = cliente.post(
        f"/api/sessoes/{sessao_id}/queixa",
        json={"queixas": ["dor-toracica", "outra"], "descricao_outra": "Zumbido"},
    )
    assert resposta.status_code == 422
    assert repositorio.fila_queixas == {}


def test_aceite_de_termo_antigo_nao_libera_a_gravacao(app, cliente, repositorio):
    sessao_id = nova_sessao(cliente)
    assert consentir(cliente, sessao_id, "medico").status_code == 201
    assert consentir(cliente, sessao_id, "paciente").status_code == 201
    servicos = app.state.servicos
    termo = servicos.conteudo.termo
    original = termo.versao
    try:
        termo.versao = "2"  # o termo mudou depois dos aceites
        resposta = cliente.post(f"/api/sessoes/{sessao_id}/audio", files={"audio": AUDIO})
    finally:
        termo.versao = original
    assert resposta.status_code == 409


def test_audio_esquecido_e_apagado_no_proximo_envio(cliente, settings):
    import os

    from app.main import IDADE_MAXIMA_AUDIO_S, PREFIXO_AUDIO

    pasta = settings.pasta_audio_temp
    pasta.mkdir(parents=True, exist_ok=True)
    esquecido = pasta / f"{PREFIXO_AUDIO}esquecido.webm"
    esquecido.write_bytes(b"audio")
    antigo = time.time() - IDADE_MAXIMA_AUDIO_S - 60
    os.utime(esquecido, (antigo, antigo))
    gravada(cliente)
    assert not esquecido.exists()
    assert arquivos_de_audio(settings) == []


@pytest.mark.parametrize("sexo", ["feminino", None])
def test_aluno_corrige_o_sexo_do_paciente_na_confirmacao(cliente, sexo):
    sessao_id = gravada(cliente)
    assert cliente.get(f"/api/sessoes/{sessao_id}").json()["sexo_paciente"] == "masculino"  # detectado
    resposta = cliente.post(
        f"/api/sessoes/{sessao_id}/queixa", json={"queixas": ["dor-toracica"], "sexo_paciente": sexo}
    )
    assert resposta.status_code == 200
    assert esperar(cliente, sessao_id, "aguardando_hipoteses")["sexo_paciente"] == sexo


def test_sexo_invalido_e_recusado(cliente):
    sessao_id = gravada(cliente)
    resposta = cliente.post(
        f"/api/sessoes/{sessao_id}/queixa", json={"queixas": ["dor-toracica"], "sexo_paciente": "x"}
    )
    assert resposta.status_code == 422


def test_colega_avisado_pelo_dono_libera_a_gravacao(cliente):
    sessao_id = nova_sessao(cliente)
    declarado = {"papel": "paciente", "nome_informado": "Ana", "versao_termo": "1", "aceito": True, "forma": "declarado_pelo_dono"}

    # Sem o aceite do dono, o aviso ao colega não vale.
    resposta = cliente.post(f"/api/sessoes/{sessao_id}/consentimentos", json=declarado)
    assert resposta.status_code == 409

    assert consentir(cliente, sessao_id, "medico").status_code == 201
    resposta = cliente.post(f"/api/sessoes/{sessao_id}/consentimentos", json=declarado)
    assert resposta.status_code == 201
    assert resposta.json()["forma"] == "declarado_pelo_dono"

    assert cliente.post(f"/api/sessoes/{sessao_id}/audio", files={"audio": AUDIO}).status_code == 200
    sessao = esperar(cliente, sessao_id, "aguardando_queixa")
    assert sorted(c["forma"] for c in sessao["consentimentos"]) == ["aceite", "declarado_pelo_dono"]


def test_aviso_do_dono_nao_vale_para_o_proprio_papel(cliente):
    sessao_id = nova_sessao(cliente)
    assert consentir(cliente, sessao_id, "medico").status_code == 201
    resposta = cliente.post(
        f"/api/sessoes/{sessao_id}/consentimentos",
        json={"papel": "medico", "nome_informado": "Rodrigo", "versao_termo": "1", "aceito": True, "forma": "declarado_pelo_dono"},
    )
    assert resposta.status_code == 409


# ---------- paciente pela IA ----------


def paciente_ia(cliente: TestClient) -> dict[str, Any]:
    resposta = cliente.post("/api/sessoes", json={"origem_caso": "paciente_ia"})
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def perguntar(cliente: TestClient, sessao_id: str, texto: str):
    return cliente.post(f"/api/sessoes/{sessao_id}/conversa", json={"texto": texto})


def test_paciente_ia_conversa_e_segue_para_a_correcao(cliente):
    sessao = paciente_ia(cliente)
    assert sessao["status"] == "conversando"
    assert sessao["cartao_id"] == "dor-toracica-teste-1"
    assert sessao["sexo_paciente"] in ("feminino", "masculino")
    assert sessao["caso_ia"] is None  # a ficha é o gabarito: escondida durante a conversa
    sessao_id = sessao["id"]

    # Não dá para encerrar sem perguntar nada.
    assert cliente.post(f"/api/sessoes/{sessao_id}/encerrar").status_code == 409

    resposta = perguntar(cliente, sessao_id, "O que te traz aqui hoje?")
    assert resposta.status_code == 200
    falas = resposta.json()["falas"]
    assert [f["papel"] for f in falas] == ["entrevistador", "paciente"]
    assert falas[1]["texto"]
    assert resposta.json()["caso_ia"] is None
    for pergunta in ["Quando começou?", "Toma algum remédio?", "Tem alergia?", "Alguém na família tem problema do coração?"]:
        assert perguntar(cliente, sessao_id, pergunta).status_code == 200

    encerrada = cliente.post(f"/api/sessoes/{sessao_id}/encerrar")
    assert encerrada.status_code == 200
    encerrada = encerrada.json()
    assert encerrada["status"] == "aguardando_queixa"
    assert encerrada["queixa_detectada"] == ["dor-toracica"]
    assert encerrada["queixa_trecho"] == "Dor no peito há 2 horas"  # a fala que cita a queixa
    assert encerrada["caso_ia"]["nome"]
    assert len(encerrada["falas"]) == 10

    # Encerrada, não aceita mais pergunta; a correção segue como na gravação.
    assert perguntar(cliente, sessao_id, "Mais alguma coisa?").status_code == 409
    assert cliente.post(f"/api/sessoes/{sessao_id}/queixa", json={"queixas": ["dor-toracica"]}).status_code == 200
    esperar(cliente, sessao_id, "aguardando_hipoteses")


def test_paciente_ia_nao_grava_audio(cliente):
    sessao_id = paciente_ia(cliente)["id"]
    assert consentir(cliente, sessao_id, "medico").status_code == 409
    assert cliente.post(f"/api/sessoes/{sessao_id}/audio", files={"audio": AUDIO}).status_code == 409


def test_paciente_ia_valida_pergunta_e_cartao(cliente):
    sessao_id = paciente_ia(cliente)["id"]
    assert perguntar(cliente, sessao_id, "").status_code == 422
    assert perguntar(cliente, sessao_id, "x" * 1001).status_code == 422
    assert perguntar(cliente, sessao_id, "   ").status_code == 422
    resposta = cliente.post("/api/sessoes", json={"origem_caso": "paciente_ia", "cartao_id": "nao-existe"})
    assert resposta.status_code == 422


def test_paciente_ia_fora_do_ar_explica(settings, repositorio):
    app = criar_app(settings, repositorio=repositorio, llm=FalsoQueFalhaUmaVez("paciente_caso"))
    with TestClient(app) as cliente:
        resposta = cliente.post("/api/sessoes", json={"origem_caso": "paciente_ia"})
        assert resposta.status_code == 503
        assert "paciente" in resposta.json()["detail"]
        sessao_id = paciente_ia(cliente)["id"]

    app = criar_app(settings, repositorio=repositorio, llm=FalsoQueFalhaUmaVez("paciente_resposta"))
    with TestClient(app) as cliente:
        resposta = perguntar(cliente, sessao_id, "O que te traz aqui?")
        assert resposta.status_code == 503
        assert cliente.get(f"/api/sessoes/{sessao_id}").json()["falas"] == []  # pergunta sem resposta não fica
        assert perguntar(cliente, sessao_id, "O que te traz aqui?").status_code == 200
