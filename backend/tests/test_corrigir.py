from datetime import date

import pytest

from app.conteudo import Conteudo
from app.pipeline.corrigir import (
    SISTEMA,
    TranscricaoNormalizada,
    calcular_notas,
    checklists_aplicaveis,
    corrigir,
    dividir_em_pedidos,
    itens_aplicaveis,
    mensagem_feito,
)
from app.schemas.sessao import Avaliacao, ChecklistUsado
from app.texto import normalizar
from tests.apoio import LLMFixo, LLMRepete, falas_exemplo


def aprovar(conteudo: Conteudo, checklist_id: str) -> Conteudo:
    checklists = dict(conteudo.checklists)
    checklists[checklist_id] = checklists[checklist_id].model_copy(
        update={"status": "aprovado", "validado_por": "Prof. Teste", "validado_em": date(2026, 9, 1)}
    )
    return Conteudo(queixas=conteudo.queixas, checklists=checklists, cartoes=conteudo.cartoes, termo=conteudo.termo)


def resposta(*itens: tuple[str, bool, list[int]]) -> dict:
    """Registros do LLM: item, feito e os números das falas citadas (a partir de 1).

    Falas de exemplo: [1] E nome, [2] P, [3] E idade, [4] P, [5] E irradiação, [6] P,
    [7] E fuma, [8] P, [9] E suor, [10] P."""
    return {"itens": [{"item_id": i, "feito": f, "falas": n, "citacao": None} for i, f, n in itens]}


def por_id(resultado) -> dict:
    return {a.item_id: a for a in resultado.avaliacoes}


def test_fala_fora_da_transcricao_vira_faltou(conteudo):
    llm = LLMRepete(resposta(("idade", True, [99])))
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    idade = por_id(resultado)["idade"]
    assert idade.status == "faltou"
    assert idade.trecho is None
    assert idade.mensagem == "Faltou perguntar a idade."


def test_feito_sem_fala_vira_faltou(conteudo):
    llm = LLMRepete(resposta(("idade", True, []), ("nome", True, [0, -1])))
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    assert por_id(resultado)["idade"].status == "faltou"
    assert por_id(resultado)["nome"].status == "faltou"


def test_item_ausente_na_resposta_vira_faltou_e_item_inventado_e_ignorado(conteudo):
    llm = LLMRepete(resposta(("item-que-nao-existe", True, [3])))
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    ids = [a.item_id for a in resultado.avaliacoes]
    assert "item-que-nao-existe" not in ids
    assert all(a.status == "faltou" for a in resultado.avaliacoes)


def test_trecho_e_montado_com_as_falas_citadas(conteudo):
    llm = LLMRepete(
        resposta(
            ("nome", True, [1]),  # só a pergunta
            ("idade", True, [3, 4]),  # pergunta e resposta
            ("tabagismo", True, [8, 7]),  # fora de ordem e repetida
        )
    )
    avaliacoes = por_id(corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True))
    assert avaliacoes["nome"].trecho == "Bom dia! Qual é o seu nome?"
    assert avaliacoes["idade"].trecho == "Quantos anos o senhor tem? Cinquenta e oito."
    assert avaliacoes["tabagismo"].trecho == "O senhor fuma? Fumo um maço por dia, sim."
    assert all(avaliacoes[i].status == "feito" for i in ("nome", "idade", "tabagismo"))


def test_fala_so_do_paciente_nao_prova_o_item(conteudo):
    """O que o paciente contou sozinho não mostra que o aluno investigou."""
    llm = LLMRepete(resposta(("idade", True, [4]), ("nome", True, [2, 4]), ("sincope", True, [10])))
    avaliacoes = por_id(corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True))
    assert avaliacoes["idade"].status == "faltou"
    assert avaliacoes["nome"].status == "faltou"
    assert avaliacoes["sincope"].status == "faltou"
    assert avaliacoes["idade"].trecho is None


def test_vale_a_primeira_pergunta_citada_sem_juntar_falas_distantes(conteudo):
    llm = LLMRepete(resposta(("idade", True, [3, 9, 10]), ("tabagismo", True, [6, 7])))
    avaliacoes = por_id(corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True))
    assert avaliacoes["idade"].trecho == "Quantos anos o senhor tem?"
    # A fala do paciente antes da pergunta fica de fora.
    assert avaliacoes["tabagismo"].trecho == "O senhor fuma?"


def test_citacao_curta_aparece_quando_esta_na_fala_do_entrevistador(conteudo):
    registros = resposta(
        ("idade", True, [3, 4]), ("nome", True, [1]), ("tabagismo", True, [7, 8]), ("irradiacao", True, [5])
    )
    citacoes = {
        "idade": "anos o senhor tem? Cinquenta",  # pergunta e começo da resposta
        "nome": "Qual é o seu nome",  # sem pontuação: confere normalizado
        "tabagismo": "Fumo um maço por dia",  # só o paciente: vão as falas inteiras
        "irradiacao": "Essa dor vai para o braço?",  # não está na fala: vão as falas inteiras
    }
    for registro in registros["itens"]:
        registro["citacao"] = citacoes[registro["item_id"]]
    avaliacoes = por_id(
        corrigir(falas_exemplo(), ["dor-toracica"], conteudo, LLMRepete(registros), contar_rascunho=True)
    )
    assert avaliacoes["idade"].trecho == "anos o senhor tem? Cinquenta"
    assert avaliacoes["nome"].trecho == "Qual é o seu nome"
    assert avaliacoes["tabagismo"].trecho == "O senhor fuma? Fumo um maço por dia, sim."
    assert avaliacoes["irradiacao"].trecho == "Essa dor vai para algum outro lugar?"


def test_citacao_sem_falas_que_provam_nao_salva_o_item(conteudo):
    registros = resposta(("idade", True, [4]))
    registros["itens"][0]["citacao"] = "Quantos anos o senhor tem?"
    assert (
        por_id(corrigir(falas_exemplo(), ["dor-toracica"], conteudo, LLMRepete(registros), contar_rascunho=True))[
            "idade"
        ].status
        == "faltou"
    )


def test_falas_vao_numeradas_para_o_llm(conteudo):
    llm = LLMRepete(resposta())
    corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    mensagem = llm.chamadas[0]["mensagem"]
    assert "[1] Entrevistador: Bom dia! Qual é o seu nome?\n[2] Paciente: Carlos Alberto." in mensagem
    assert "[10] Paciente: Não, suor não." in mensagem


def test_normalizacao_mantem_acentos_e_palavras_inteiras():
    transcricao = TranscricaoNormalizada.de(falas_exemplo())
    assert normalizar("  Qual é o SEU nome?! ") == "qual é o seu nome"
    assert not transcricao.tem("qual e o seu nome")  # sem acento não é o mesmo texto
    assert not transcricao.tem("anos o sen")  # pedaço de palavra não vale
    assert not transcricao.tem("sim")  # curto demais para provar algo
    assert transcricao.tem("Quantos anos o senhor tem? Cinquenta e oito.")  # pergunta e resposta


def test_trecho_escrito_precisa_pegar_fala_do_entrevistador():
    transcricao = TranscricaoNormalizada.de(falas_exemplo())
    assert transcricao.mostra_entrevistador("Quantos anos o senhor tem? Cinquenta e oito.")
    assert transcricao.mostra_entrevistador("o senhor fuma")
    assert transcricao.tem("Cinquenta e oito.")
    assert not transcricao.mostra_entrevistador("Cinquenta e oito.")  # só o paciente
    assert not transcricao.mostra_entrevistador("tem? Cinquenta e oito")  # pedaço curto demais da pergunta
    assert not transcricao.mostra_entrevistador("Qual é a sua idade?")  # não existe


def test_item_repetido_entre_checklists_conta_uma_vez(conteudo):
    llm = LLMRepete(resposta(("tabagismo", True, [7])))
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    tabagismo = [a for a in resultado.avaliacoes if a.item_id == "tabagismo"]
    assert len(tabagismo) == 1
    assert tabagismo[0].checklist_id == "geral"
    # O LLM recebe o item uma vez só.
    ids_enviados = [i["id"] for i in llm.chamadas[0]["contexto"]["itens"]]
    assert ids_enviados.count("tabagismo") == 1
    assert len(resultado.avaliacoes) == 7


def test_notas_com_rascunho_contando_sao_provisorias(conteudo):
    llm = LLMRepete(
        resposta(
            ("nome", True, [1]),  # geral, peso 2
            ("idade", True, [3]),  # geral, peso 3
            ("tabagismo", True, [7]),  # geral, peso 3
            ("alergias", False, []),  # geral, peso 2
            ("irradiacao", True, [5]),  # queixa, peso 3
            ("sudorese", False, []),  # queixa, peso 2
            ("sincope", False, []),  # queixa, peso 2
        )
    )
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    assert resultado.notas.geral == 80  # 8 de 10
    assert resultado.notas.queixa == 43  # 3 de 7 = 42,86
    assert resultado.notas.provisoria is True
    assert all(a.conta_na_nota for a in resultado.avaliacoes)


def test_arredondamento(conteudo):
    # geral: nome (2) + idade (3) feitos de 10 = 50; queixa: sudorese (2) de 7 = 28,57 -> 29
    llm = LLMRepete(
        resposta(
            ("nome", True, [1]),
            ("idade", True, [3]),
            ("sudorese", True, [9]),
        )
    )
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    assert resultado.notas.geral == 50
    assert resultado.notas.queixa == 29


def test_arredondamento_meio_sobe():
    def avaliacao(item_id: str, status: str, peso: int) -> Avaliacao:
        return Avaliacao(
            item_id=item_id,
            checklist_id="geral",
            secao="S",
            texto="T",
            status=status,
            trecho="x" if status == "feito" else None,
            mensagem="m",
            peso=peso,
            conta_na_nota=True,
        )

    avaliacoes = [avaliacao("a", "feito", 1), avaliacao("b", "faltou", 3), avaliacao("c", "faltou", 4)]
    usados = [ChecklistUsado(id="geral", versao=1, status="aprovado", conta_na_nota=True)]
    notas = calcular_notas(avaliacoes, usados, {"geral": "geral"})
    assert notas.geral == 13  # 1 de 8 = 12,5
    assert notas.queixa is None
    assert notas.provisoria is False


def test_rascunho_nao_conta_sem_contar_rascunho(conteudo):
    llm = LLMRepete(resposta(("idade", True, [3])))
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=False)
    assert resultado.notas.geral is None
    assert resultado.notas.queixa is None
    assert resultado.notas.provisoria is False
    assert not any(a.conta_na_nota for a in resultado.avaliacoes)
    # O item continua corrigido e aparece como sugestão, fora da nota.
    assert por_id(resultado)["idade"].status == "feito"
    assert all(not c.conta_na_nota for c in resultado.checklists_usados)


def test_so_aprovado_conta_sem_contar_rascunho(conteudo):
    conteudo = aprovar(conteudo, "geral")
    llm = LLMRepete(resposta(("idade", True, [3])))
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=False)
    assert resultado.notas.geral == 30  # 3 de 10
    assert resultado.notas.queixa is None  # dor torácica ainda é rascunho
    assert resultado.notas.provisoria is False


def test_aprovado_com_rascunho_contando(conteudo):
    conteudo = aprovar(conteudo, "geral")
    llm = LLMRepete(resposta(("idade", True, [3])))
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    assert resultado.notas.queixa == 0
    assert resultado.notas.provisoria is True  # a nota da queixa veio de rascunho


def test_registra_checklists_usados(conteudo):
    llm = LLMRepete(resposta())
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    usados = [(c.id, c.versao, c.status, c.conta_na_nota) for c in resultado.checklists_usados]
    assert usados == [("geral", 3, "rascunho", True), ("dor-toracica", 2, "rascunho", True)]


def test_outra_e_queixa_sem_checklist_usam_so_o_geral(conteudo):
    assert [c.id for c in checklists_aplicaveis(["outra"], conteudo)] == ["geral"]
    assert [c.id for c in checklists_aplicaveis(["cefaleia"], conteudo)] == ["geral"]
    llm = LLMRepete(resposta())
    resultado = corrigir(falas_exemplo(), ["outra"], conteudo, llm, contar_rascunho=True)
    assert {a.checklist_id for a in resultado.avaliacoes} == {"geral"}
    assert resultado.notas.queixa is None
    assert resultado.notas.geral == 0


def test_mensagens(conteudo):
    llm = LLMRepete(resposta(("idade", True, [3])))
    avaliacoes = por_id(corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True))
    assert avaliacoes["idade"].mensagem == "Você investigou: idade."
    assert avaliacoes["alergias"].mensagem == "Faltou perguntar sobre alergias."
    assert avaliacoes["alergias"].secao == "Hábitos e antecedentes"
    assert mensagem_feito("HAS e DM.") == "Você investigou: HAS e DM."


def test_correcao_pede_ao_llm_sem_palavras_chave_no_prompt(conteudo):
    llm = LLMRepete(resposta())
    corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    chamada = llm.chamadas[0]
    assert chamada["tarefa"] == "corrigir"
    assert "palavras_chave" not in chamada["mensagem"]
    assert "Entrevistador: Quantos anos o senhor tem?" in chamada["mensagem"]


@pytest.mark.parametrize("contar", [True, False])
def test_toda_avaliacao_feita_tem_trecho_que_existe_e_mostra_o_entrevistador(conteudo, contar):
    llm = LLMRepete(
        resposta(
            ("nome", True, [1, 2]),
            ("idade", True, [4]),
            ("tabagismo", True, [70]),
            ("sincope", True, []),
            ("irradiacao", False, [5]),  # não feito: as falas citadas não importam
        )
    )
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=contar)
    transcricao = TranscricaoNormalizada.de(falas_exemplo())
    for avaliacao in resultado.avaliacoes:
        if avaliacao.status == "feito":
            assert transcricao.mostra_entrevistador(avaliacao.trecho)
        else:
            assert avaliacao.trecho is None
    assert [a.item_id for a in resultado.avaliacoes if a.status == "feito"] == ["nome"]


# ---------- um pedido por checklist ----------


def _ids_pedidos(chamada) -> list[str]:
    return [i["id"] for i in chamada["contexto"]["itens"]]


def test_um_pedido_por_checklist_com_os_itens_de_cada_um(conteudo):
    llm = LLMRepete(resposta())
    corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True)
    assert len(llm.chamadas) == 2
    geral, queixa = llm.chamadas
    assert _ids_pedidos(geral) == ["nome", "idade", "tabagismo", "alergias"]
    # 'tabagismo' também está no checklist da queixa, mas conta uma vez só, no geral.
    assert _ids_pedidos(queixa) == ["irradiacao", "sudorese", "sincope"]
    assert "Checklist geral" in geral["mensagem"]
    assert "específico da queixa" in queixa["mensagem"]
    assert "Entrevistador: Quantos anos o senhor tem?" in queixa["mensagem"]


def test_outra_faz_um_pedido_so(conteudo):
    llm = LLMRepete(resposta())
    corrigir(falas_exemplo(), ["outra"], conteudo, llm, contar_rascunho=True)
    assert len(llm.chamadas) == 1


def test_a_mesma_fala_vale_no_geral_e_na_queixa(conteudo):
    """O que dava nota 0 na queixa: um trecho que já provou um item do geral vale também no da queixa."""
    fala = "Essa dor vai para algum outro lugar?"
    llm = LLMFixo(resposta(("idade", True, [5])), resposta(("irradiacao", True, [5])))
    avaliacoes = por_id(corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True))
    assert avaliacoes["idade"].status == "feito"
    assert avaliacoes["irradiacao"].status == "feito"
    assert avaliacoes["irradiacao"].trecho == fala


def test_registro_de_item_que_nao_foi_pedido_e_ignorado(conteudo):
    # O pedido do geral responde por um item da queixa; só vale o que o pedido da queixa disse.
    llm = LLMFixo(
        resposta(("irradiacao", True, [5])),
        resposta(("irradiacao", False, [])),
    )
    avaliacoes = por_id(corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True))
    assert avaliacoes["irradiacao"].status == "faltou"


def test_instrucoes_deixam_a_mesma_fala_provar_varios_itens():
    assert "A mesma fala pode provar vários itens" in SISTEMA
    assert "outras palavras" in SISTEMA


def test_instrucoes_dizem_ate_onde_vale_a_pergunta_aberta():
    assert "mesmo aberta" in SISTEMA
    assert "fora da resposta à pergunta, não basta" in SISTEMA


# ---------- pedidos menores ----------


def test_dividir_em_pedidos_respeita_o_limite_e_junta_secoes(conteudo):
    geral = itens_aplicaveis([conteudo.checklist_geral], contar_rascunho=True)
    assert [len(p) for p in dividir_em_pedidos(geral, 0)] == [len(geral)]
    assert dividir_em_pedidos([], 3) == []
    for limite in (1, 2, 3):
        pedidos = dividir_em_pedidos(geral, limite)
        assert all(0 < len(p) <= limite for p in pedidos)
        assert [a.item.id for p in pedidos for a in p] == [a.item.id for a in geral]  # nada some nem troca de ordem


def test_secao_que_cabe_inteira_nao_e_partida(conteudo):
    geral = itens_aplicaveis([conteudo.checklist_geral], contar_rascunho=True)
    secoes = [s.titulo for s in conteudo.checklist_geral.secoes]
    maior = max(sum(1 for a in geral if a.secao.titulo == t) for t in secoes)
    for pedido in dividir_em_pedidos(geral, maior):
        for titulo in {a.secao.titulo for a in pedido}:
            # Cada seção presente no pedido está inteira nele.
            assert sum(1 for a in pedido if a.secao.titulo == titulo) == sum(
                1 for a in geral if a.secao.titulo == titulo
            )


def test_corrigir_em_pedidos_menores_da_o_mesmo_resultado(conteudo):
    registros = resposta(("nome", True, [1]), ("idade", True, [3, 4]), ("irradiacao", True, [5]))
    inteiro = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, LLMRepete(registros), contar_rascunho=True)
    llm = LLMRepete(registros)
    em_partes = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True, itens_por_pedido=1)
    assert len(llm.chamadas) == 7  # um item por pedido
    assert em_partes.avaliacoes == inteiro.avaliacoes
    assert em_partes.notas == inteiro.notas


# ---------- itens de um sexo só ----------


def _com_sincope_so_feminino(conteudo: Conteudo) -> Conteudo:
    checklists = dict(conteudo.checklists)
    queixa = checklists["dor-toracica"]
    secoes = [
        s.model_copy(
            update={"itens": [i.model_copy(update={"sexo": "feminino"}) if i.id == "sincope" else i for i in s.itens]}
        )
        for s in queixa.secoes
    ]
    checklists["dor-toracica"] = queixa.model_copy(update={"secoes": secoes})
    return Conteudo(queixas=conteudo.queixas, checklists=checklists, cartoes=conteudo.cartoes, termo=conteudo.termo)


@pytest.mark.parametrize("sexo, tem_sincope", [("masculino", False), ("feminino", True), (None, True)])
def test_item_so_de_um_sexo_sai_quando_o_paciente_e_do_outro(conteudo, sexo, tem_sincope):
    conteudo = _com_sincope_so_feminino(conteudo)
    llm = LLMRepete(resposta())
    resultado = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, llm, contar_rascunho=True, sexo_paciente=sexo)
    assert ("sincope" in por_id(resultado)) is tem_sincope
    # O LLM nem recebe o item que não vale.
    assert ("sincope" in _ids_pedidos(llm.chamadas[1])) is tem_sincope


def test_item_que_nao_vale_nao_pesa_na_nota(conteudo):
    conteudo = _com_sincope_so_feminino(conteudo)
    registros = resposta(("irradiacao", True, [5]), ("sudorese", True, [9]))
    homem = corrigir(
        falas_exemplo(),
        ["dor-toracica"],
        conteudo,
        LLMRepete(registros),
        contar_rascunho=True,
        sexo_paciente="masculino",
    )
    sem_saber = corrigir(falas_exemplo(), ["dor-toracica"], conteudo, LLMRepete(registros), contar_rascunho=True)
    assert homem.notas.queixa == 100  # irradiação e sudorese, os dois que valem
    assert sem_saber.notas.queixa < 100
