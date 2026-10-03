"""Painel de atividade: acesso só do administrador e números certos."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.auth import Usuario, e_admin, usuario_atual
from app.main import criar_app
from app.painel import montar_painel
from app.schemas.painel import ContaPainel
from app.schemas.sessao import Notas, Sessao


def _sessao(dono: str, dias_atras: int, origem: str = "inventado", nota: int | None = None, **extra) -> Sessao:
    agora = datetime(2026, 10, 3, 15, tzinfo=UTC)
    return Sessao(
        id=f"{dono}-{dias_atras}-{origem}",
        dono_id=dono,
        criada_em=agora - timedelta(days=dias_atras),
        status="concluida" if nota is not None else "criada",
        origem_caso=origem,
        notas=Notas(geral=nota, queixa=None, provisoria=True) if nota is not None else None,
        **extra,
    )


def test_admin_por_email(settings):
    settings = settings.model_copy(update={"auth": "supabase", "admin_emails": "Dono@Exemplo.com, outro@x.com"})
    assert e_admin(settings, Usuario(id="1", email="dono@exemplo.com"))
    assert not e_admin(settings, Usuario(id="2", email="aluno@exemplo.com"))
    assert not e_admin(settings, Usuario(id="3"))
    assert not e_admin(settings.model_copy(update={"admin_emails": ""}), Usuario(id="1", email="dono@exemplo.com"))


def test_montar_painel_junta_contas_e_sessoes():
    agora = datetime(2026, 10, 3, 18, tzinfo=UTC)
    contas = [ContaPainel(id="a", email="a@x.com"), ContaPainel(id="b", email="b@x.com"), ContaPainel(id="c")]
    sessoes = [
        _sessao("a", 0, nota=80, queixas_confirmadas=["cefaleia"]),
        _sessao("a", 2, "paciente_ia", nota=60, queixas_confirmadas=["cefaleia"]),
        _sessao("b", 10, nota=70, queixas_confirmadas=["dispneia"]),
        _sessao("fantasma", 1),
    ]
    painel = montar_painel(contas, sessoes, True, agora)

    assert painel.resumo.contas == 4
    assert painel.resumo.sessoes == 4
    assert painel.resumo.sessoes_7_dias == 3
    assert painel.resumo.ativas_7_dias == 2
    assert painel.resumo.paciente_ia == 1
    assert painel.resumo.concluidas == 3
    a = next(c for c in painel.contas if c.id == "a")
    assert (a.sessoes, a.com_colega, a.paciente_ia, a.media_geral) == (2, 1, 1, 70)
    assert painel.contas[0].id == "a"  # quem mexeu por último vem primeiro
    assert next(c for c in painel.contas if c.id == "c").sessoes == 0
    assert len(painel.por_dia) == 14 and painel.por_dia[-1].sessoes == 1
    assert painel.queixas[0].queixa == "cefaleia" and painel.queixas[0].vezes == 2


def test_painel_no_modo_demonstracao(settings):
    with TestClient(criar_app(settings)) as cliente:
        assert cliente.get("/api/eu/acesso").json() == {"admin": True}
        cliente.post("/api/sessoes", json={"origem_caso": "inventado"})
        painel = cliente.get("/api/painel").json()
    assert painel["resumo"]["sessoes"] == 1
    assert painel["contas_completas"] is False
    assert painel["contas"][0]["nome"] == "Aluno de demonstração"
    assert "falas" not in painel["recentes"][0]


def test_painel_fechado_para_aluno(settings):
    settings = settings.model_copy(update={"auth": "supabase", "admin_emails": "dono@exemplo.com"})
    app = criar_app(settings)
    app.dependency_overrides[usuario_atual] = lambda: Usuario(id="aluno", email="aluno@exemplo.com")
    with TestClient(app) as cliente:
        assert cliente.get("/api/eu/acesso").json() == {"admin": False}
        resposta = cliente.get("/api/painel")
    assert resposta.status_code == 403
