"""Rotas da API do AnamneLab (contrato em docs/api.md)."""

import logging
import random
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.auth import Usuario, usuario_atual
from app.config import Settings, obter_settings
from app.conteudo import QUEIXA_OUTRA, ErroConteudo
from app.llm import ClienteLLM, ErroLLM
from app.pipeline.comum import ErroPipeline
from app.pipeline.corrigir import ErroContestacao, contestar, item_do_checklist
from app.pipeline.paciente_ia import montar_caso, responder
from app.pipeline.transcrever import (
    ErroTranscricao,
    Transcritor,
    apagar_audio,
    montar_dica,
    transcrever_pergunta_e_apagar,
)
from app.pipeline.voz import ErroVoz, VozPaciente
from app.processamento import Processador
from app.repositorio import Repositorio
from app.schemas.conteudo import Cartao, Queixa
from app.schemas.llm import Fala
from app.schemas.sessao import (
    Consentimento,
    ConsentimentoCriar,
    ContestacaoCriar,
    HipotesesAluno,
    PerguntaPaciente,
    QueixaConfirmar,
    Saude,
    Sessao,
    SessaoCriar,
    SessaoResumo,
    Termo,
    TranscricaoEditar,
)
from app.servicos import Servicos, montar_servicos
from app.texto import normalizar

logger = logging.getLogger("app")

PREFIXO_AUDIO = "anamnelab-"
IDADE_MAXIMA_AUDIO_S = 2 * 60 * 60
"""Nenhum áudio leva mais que isso para ser transcrito; mais velho que isso é sobra."""
TAMANHO_MAXIMO_PERGUNTA = 5 * 1024 * 1024
"""Uma pergunta falada tem segundos; 5 MB passam de vários minutos no formato do app."""

TIPOS_AUDIO = {
    "audio/webm": ".webm",
    "video/webm": ".webm",
    "audio/ogg": ".ogg",
    "application/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/m4a": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/vnd.wave": ".wav",
}
EXTENSOES_AUDIO = {
    ".webm": ".webm",
    ".ogg": ".ogg",
    ".oga": ".ogg",
    ".m4a": ".m4a",
    ".mp4": ".m4a",
    ".mp3": ".mp3",
    ".mpeg": ".mp3",
    ".wav": ".wav",
}

MENSAGEM_NAO_ENCONTRADA = "Sessão não encontrada."
MENSAGEM_ERRO_INTERNO = "Algo deu errado do nosso lado. Tente de novo em alguns minutos."


# ---------- middlewares ----------


class ProtegerErros:
    """Erro inesperado vira 500 com mensagem em PT-BR. No log, só a rota e o tipo do erro."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        iniciou = False

        async def enviar(mensagem) -> None:
            nonlocal iniciou
            if mensagem["type"] == "http.response.start":
                iniciou = True
            await send(mensagem)

        try:
            await self.app(scope, receive, enviar)
        except Exception as erro:
            logger.error("erro inesperado (rota=%s, erro=%s)", scope.get("path"), type(erro).__name__)
            if not iniciou:
                await JSONResponse({"detail": MENSAGEM_ERRO_INTERNO}, status_code=500)(scope, receive, send)


class LimiteAudio:
    """Recusa o envio de áudio grande antes de ler o corpo, quando o tamanho vem no cabeçalho."""

    def __init__(self, app, limite_bytes: int) -> None:
        self.app = app
        self.limite_bytes = limite_bytes
        self.limite = limite_bytes + 1024 * 1024  # folga para o envelope multipart

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http" and scope["method"] == "POST" and scope["path"].endswith("/audio"):
            cabecalhos = dict(scope.get("headers") or [])
            tamanho = cabecalhos.get(b"content-length")
            if tamanho and tamanho.isdigit() and int(tamanho) > self.limite:
                resposta = JSONResponse({"detail": _mensagem_tamanho(self.limite_bytes)}, status_code=413)
                await resposta(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _mensagem_tamanho(limite_bytes: int) -> str:
    megas = round(limite_bytes / (1024 * 1024))
    return f"A gravação passou do limite de {megas} MB. Grave de novo, num tempo menor."


# ---------- ajudantes ----------


def _servicos(request: Request) -> Servicos:
    return request.app.state.servicos


def _processador(request: Request) -> Processador:
    return request.app.state.processador


ServicosDep = Annotated[Servicos, Depends(_servicos)]
UsuarioDep = Annotated[Usuario, Depends(usuario_atual)]


def _agora() -> datetime:
    return datetime.now(UTC)


def _sessao_do_dono(servicos: Servicos, sessao_id: str, usuario: Usuario) -> Sessao:
    """Só o dono enxerga a sessão; para os outros ela não existe (404)."""
    sessao = servicos.repositorio.obter_sessao(sessao_id)
    if sessao is None or sessao.dono_id != usuario.id:
        raise HTTPException(404, MENSAGEM_NAO_ENCONTRADA)
    return sessao


def correcao_liberada(sessao: Sessao) -> bool:
    """O aluno escreve as hipóteses antes de ver a correção."""
    return bool(sessao.hipoteses_aluno)


def para_aluno(sessao: Sessao) -> Sessao:
    # A ficha do paciente pela IA é o gabarito do caso: só aparece depois da conversa.
    oculto = {"caso_ia": None} if sessao.status == "conversando" else {}
    if correcao_liberada(sessao):
        return sessao.model_copy(update=oculto) if oculto else sessao
    return sessao.model_copy(update={"avaliacoes": [], "notas": None, "sugestoes": None, **oculto})


def _recarregar(servicos: Servicos, sessao_id: str) -> Sessao:
    sessao = servicos.repositorio.obter_sessao(sessao_id)
    if sessao is None:
        raise HTTPException(404, MENSAGEM_NAO_ENCONTRADA)
    return para_aluno(sessao)


def _extensao_audio(arquivo: UploadFile) -> str | None:
    tipo = (arquivo.content_type or "").split(";")[0].strip().lower()
    if tipo in TIPOS_AUDIO:
        return TIPOS_AUDIO[tipo]
    sufixo = Path(arquivo.filename or "").suffix.lower()
    return EXTENSOES_AUDIO.get(sufixo)


def preparar_pasta_audio(pasta: Path) -> None:
    """Cria a pasta temporária e apaga áudios que sobraram de uma parada brusca."""
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    for sobra in pasta.glob(f"{PREFIXO_AUDIO}*"):
        apagar_audio(sobra)


def apagar_audios_antigos(pasta: Path, idade_maxima_s: float = IDADE_MAXIMA_AUDIO_S) -> None:
    """Rede de segurança: apaga áudio esquecido (tarefa em segundo plano que não rodou)."""
    limite = time.time() - idade_maxima_s
    for sobra in pasta.glob(f"{PREFIXO_AUDIO}*"):
        try:
            antigo = sobra.stat().st_mtime < limite
        except OSError:
            continue
        if antigo:
            apagar_audio(sobra)


# ---------- rotas ----------

rotas = APIRouter(prefix="/api")


@rotas.get("/saude", response_model=Saude)
def saude(servicos: ServicosDep) -> Saude:
    settings = servicos.settings
    demonstracao = settings.llm_provedor == "falso" or settings.transcricao == "falso"
    vozes = servicos.voz.sexos if servicos.voz else []
    return Saude(ok=True, modo_demonstracao=demonstracao, vozes_paciente=vozes)


@rotas.get("/queixas", response_model=list[Queixa])
def listar_queixas(servicos: ServicosDep) -> list[Queixa]:
    return servicos.conteudo.queixas.queixas


@rotas.get("/cartoes/sortear", response_model=Cartao)
def sortear_cartao(servicos: ServicosDep, queixa: str | None = None) -> Cartao:
    cartoes = [c for c in servicos.conteudo.cartoes.cartoes if queixa is None or c.queixa == queixa]
    if not cartoes:
        raise HTTPException(404, "Ainda não há cartões para essa queixa.")
    return random.choice(cartoes)


@rotas.get("/termo", response_model=Termo)
def termo_vigente(servicos: ServicosDep) -> Termo:
    return servicos.conteudo.termo


@rotas.get("/sessoes", response_model=list[SessaoResumo])
def listar_sessoes(servicos: ServicosDep, usuario: UsuarioDep) -> list[SessaoResumo]:
    return [
        SessaoResumo(
            id=s.id,
            criada_em=s.criada_em,
            status=s.status,
            queixas_confirmadas=s.queixas_confirmadas,
            notas=s.notas if correcao_liberada(s) else None,
        )
        for s in servicos.repositorio.listar_sessoes(usuario.id)
    ]


@rotas.post("/sessoes", response_model=Sessao, status_code=201)
def criar_sessao(corpo: SessaoCriar, servicos: ServicosDep, usuario: UsuarioDep) -> Sessao:
    if corpo.origem_caso == "paciente_ia":
        return _criar_sessao_paciente_ia(corpo, servicos, usuario)
    cartao_id = corpo.cartao_id
    if corpo.origem_caso == "cartao":
        if not cartao_id:
            raise HTTPException(422, "Escolha o cartão do caso antes de começar.")
        if cartao_id not in {c.id for c in servicos.conteudo.cartoes.cartoes}:
            raise HTTPException(422, "Esse cartão não existe. Sorteie outro.")
    else:
        cartao_id = None
    sessao = Sessao(
        id=str(uuid.uuid4()),
        dono_id=usuario.id,
        criada_em=_agora(),
        status="criada",
        origem_caso=corpo.origem_caso,
        cartao_id=cartao_id,
    )
    servicos.repositorio.criar_sessao(sessao)
    return sessao


MENSAGEM_PACIENTE_FORA = "O paciente não respondeu agora. Tente de novo em alguns instantes."


def _criar_sessao_paciente_ia(corpo: SessaoCriar, servicos: ServicosDep, usuario: Usuario) -> Sessao:
    """Sorteia (ou usa) um cartão e monta a ficha do paciente que a IA vai interpretar."""
    cartoes = servicos.conteudo.cartoes.cartoes
    if corpo.cartao_id:
        cartao = next((c for c in cartoes if c.id == corpo.cartao_id), None)
        if cartao is None:
            raise HTTPException(422, "Esse cartão não existe. Sorteie outro.")
    else:
        cartao = random.choice(cartoes)
    try:
        caso = montar_caso(cartao, servicos.llm)
    except ErroLLM:
        logger.warning("paciente pela IA: ficha não montada")
        raise HTTPException(503, "Não deu para chamar o paciente agora. Tente de novo em alguns minutos.") from None
    sessao = Sessao(
        id=str(uuid.uuid4()),
        dono_id=usuario.id,
        criada_em=_agora(),
        status="conversando",
        origem_caso="paciente_ia",
        cartao_id=cartao.id,
        sexo_paciente=caso.sexo,
        caso_ia=caso,
    )
    servicos.repositorio.criar_sessao(sessao)
    return para_aluno(sessao)


def _em_conversa(servicos: Servicos, sessao_id: str, usuario: Usuario) -> Sessao:
    sessao = _sessao_do_dono(servicos, sessao_id, usuario)
    if sessao.status != "conversando" or sessao.caso_ia is None:
        raise HTTPException(409, "Esta consulta já foi encerrada.")
    return sessao


@rotas.post("/sessoes/{sessao_id}/conversa", response_model=Sessao)
def perguntar_ao_paciente(
    sessao_id: str, corpo: PerguntaPaciente, servicos: ServicosDep, usuario: UsuarioDep
) -> Sessao:
    sessao = _em_conversa(servicos, sessao_id, usuario)
    return _perguntar(servicos, sessao, corpo.texto)


def _perguntar(servicos: Servicos, sessao: Sessao, texto: str) -> Sessao:
    """Manda a pergunta ao paciente pela IA e guarda a pergunta e a resposta nas falas."""
    assert sessao.caso_ia is not None
    try:
        resposta = responder(sessao.caso_ia, sessao.falas, texto, servicos.llm)
    except ErroPipeline as erro:
        raise HTTPException(422, erro.mensagem) from None
    except ErroLLM:
        logger.warning("paciente pela IA: sem resposta (sessao=%s)", sessao.id)
        raise HTTPException(503, MENSAGEM_PACIENTE_FORA) from None
    falas = [*sessao.falas, Fala(papel="entrevistador", texto=texto.strip()), Fala(papel="paciente", texto=resposta)]
    servicos.repositorio.salvar_transcricao(sessao.id, falas, editada=False)
    return _recarregar(servicos, sessao.id)


@rotas.post("/sessoes/{sessao_id}/conversa/audio", response_model=Sessao)
def perguntar_falando(
    sessao_id: str,
    servicos: ServicosDep,
    usuario: UsuarioDep,
    audio: Annotated[UploadFile, File()],
) -> Sessao:
    """Pergunta falada: o Whisper transcreve, o áudio é apagado e a pergunta segue como a escrita."""
    sessao = _em_conversa(servicos, sessao_id, usuario)
    versao_termo = servicos.conteudo.termo.versao
    if not any(c.forma == "aceite" and c.versao_termo == versao_termo for c in sessao.consentimentos):
        raise HTTPException(409, "Antes de falar com o paciente, aceite o termo de gravação.")
    extensao = _extensao_audio(audio)
    if extensao is None:
        raise HTTPException(415, "Formato de áudio não aceito. Use webm, ogg, m4a, mp3 ou wav.")

    pasta = servicos.settings.pasta_audio_temp
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    caminho = pasta / f"{PREFIXO_AUDIO}{secrets.token_hex(16)}{extensao}"
    try:
        total = 0
        with caminho.open("wb") as destino:
            while bloco := audio.file.read(1024 * 1024):
                total += len(bloco)
                if total > TAMANHO_MAXIMO_PERGUNTA:
                    raise HTTPException(413, "A pergunta ficou longa demais. Fale uma pergunta de cada vez.")
                destino.write(bloco)
        if total == 0:
            raise HTTPException(422, "Não deu para ouvir a pergunta. Segure o botão enquanto fala.")
        numero = sum(1 for f in sessao.falas if f.papel == "entrevistador")
        texto = transcrever_pergunta_e_apagar(
            caminho, servicos.transcritor, numero=numero, dica=montar_dica(servicos.conteudo.queixas)
        )
    except ErroTranscricao:
        raise HTTPException(422, "Não deu para entender a pergunta. Fale de novo, perto do microfone.") from None
    finally:
        apagar_audio(caminho)
    return _perguntar(servicos, sessao, texto)


@rotas.get("/sessoes/{sessao_id}/voz/{indice}")
def voz_do_paciente(sessao_id: str, indice: int, servicos: ServicosDep, usuario: UsuarioDep) -> Response:
    """A fala de número `indice` do paciente pela IA, com a voz do backend (Edge ou Piper)."""
    sessao = _sessao_do_dono(servicos, sessao_id, usuario)
    if servicos.voz is None:
        raise HTTPException(404, "A voz do paciente fica com o navegador neste app.")
    if sessao.origem_caso != "paciente_ia" or not 0 <= indice < len(sessao.falas):
        raise HTTPException(404, "Fala não encontrada.")
    fala = sessao.falas[indice]
    if fala.papel != "paciente":
        raise HTTPException(404, "Fala não encontrada.")
    sexo = sessao.caso_ia.sexo if sessao.caso_ia else (sessao.sexo_paciente or "feminino")
    try:
        wav = servicos.voz.falar(fala.texto, sexo)
    except ErroVoz:
        raise HTTPException(503, "A voz do paciente não saiu agora. A resposta está escrita na tela.") from None
    return Response(
        content=wav, media_type=servicos.voz.tipo_audio, headers={"Cache-Control": "private, max-age=3600"}
    )


@rotas.post("/sessoes/{sessao_id}/encerrar", response_model=Sessao)
def encerrar_conversa(sessao_id: str, servicos: ServicosDep, usuario: UsuarioDep) -> Sessao:
    """Fim da entrevista: a queixa do cartão vem sugerida e o aluno confirma, como na gravação."""
    sessao = _em_conversa(servicos, sessao_id, usuario)
    if not any(f.papel == "entrevistador" for f in sessao.falas):
        raise HTTPException(409, "Faça pelo menos uma pergunta antes de encerrar.")
    cartao = next((c for c in servicos.conteudo.cartoes.cartoes if c.id == sessao.cartao_id), None)
    da_biblioteca = next((q for q in servicos.conteudo.queixas.queixas if cartao and q.id == cartao.queixa), None)
    queixa = [da_biblioteca.id] if da_biblioteca else []
    # Trecho: a primeira fala do paciente que fala da queixa (nome ou sinônimo); sem ela, nenhum.
    termos = [normalizar(t) for t in ([da_biblioteca.nome, *da_biblioteca.sinonimos] if da_biblioteca else [])]
    trecho = next(
        (
            f.texto
            for f in sessao.falas
            if f.papel == "paciente" and any(t and t in normalizar(f.texto) for t in termos)
        ),
        None,
    )
    servicos.repositorio.atualizar_sessao(
        sessao_id,
        status="aguardando_queixa",
        progresso=100,
        mensagem_erro=None,
        queixa_detectada=queixa,
        queixa_trecho=trecho,
    )
    return _recarregar(servicos, sessao_id)


@rotas.get("/sessoes/{sessao_id}", response_model=Sessao)
def obter_sessao(sessao_id: str, servicos: ServicosDep, usuario: UsuarioDep) -> Sessao:
    return para_aluno(_sessao_do_dono(servicos, sessao_id, usuario))


@rotas.delete("/sessoes/{sessao_id}", status_code=204)
def apagar_sessao(sessao_id: str, servicos: ServicosDep, usuario: UsuarioDep) -> Response:
    _sessao_do_dono(servicos, sessao_id, usuario)
    servicos.repositorio.apagar_sessao(sessao_id)
    return Response(status_code=204)


def _antes_da_gravacao(sessao: Sessao) -> bool:
    """Sessão nova, ou que falhou ainda no áudio (dá para gravar de novo)."""
    return sessao.status == "criada" or (sessao.status == "erro" and not sessao.falas)


@rotas.post("/sessoes/{sessao_id}/consentimentos", response_model=Consentimento, status_code=201)
def registrar_consentimento(
    sessao_id: str, corpo: ConsentimentoCriar, servicos: ServicosDep, usuario: UsuarioDep
) -> Consentimento:
    sessao = _sessao_do_dono(servicos, sessao_id, usuario)
    # No paciente pela IA, o aceite vem antes da primeira pergunta falada; não há colega.
    falando = sessao.status == "conversando" and corpo.forma == "aceite"
    if not _antes_da_gravacao(sessao) and not falando:
        raise HTTPException(409, "O aceite é registrado antes da gravação, e esta sessão já foi gravada.")
    if corpo.versao_termo != servicos.conteudo.termo.versao:
        raise HTTPException(409, "O termo de gravação mudou. Leia a versão atual e aceite de novo.")
    nome = corpo.nome_informado.strip()
    if not nome:
        raise HTTPException(422, "Escreva o nome de quem está aceitando o termo.")
    if corpo.forma == "declarado_pelo_dono" and not any(
        c.forma == "aceite" and c.papel != corpo.papel and c.versao_termo == corpo.versao_termo
        for c in sessao.consentimentos
    ):
        raise HTTPException(409, "Primeiro, quem abriu a sessão aceita o termo de gravação.")
    consentimento = Consentimento(
        id=str(uuid.uuid4()),
        sessao_id=sessao_id,
        papel=corpo.papel,
        nome_informado=nome,
        versao_termo=corpo.versao_termo,
        aceito_em=_agora(),
        forma=corpo.forma,
    )
    servicos.repositorio.adicionar_consentimento(consentimento)
    return consentimento


@rotas.post("/sessoes/{sessao_id}/audio", response_model=Sessao)
def enviar_audio(
    sessao_id: str,
    request: Request,
    tarefas: BackgroundTasks,
    servicos: ServicosDep,
    usuario: UsuarioDep,
    audio: Annotated[UploadFile, File()],
) -> Sessao:
    sessao = _sessao_do_dono(servicos, sessao_id, usuario)
    versao_termo = servicos.conteudo.termo.versao
    papeis = {c.papel for c in sessao.consentimentos if c.versao_termo == versao_termo}
    if not {"medico", "paciente"} <= papeis:
        raise HTTPException(409, "Antes de gravar, quem faz o médico e quem faz o paciente precisam aceitar o termo.")
    if not _antes_da_gravacao(sessao):
        raise HTTPException(409, "Esta sessão já tem gravação. Abra uma sessão nova para gravar outra.")
    extensao = _extensao_audio(audio)
    if extensao is None:
        raise HTTPException(415, "Formato de áudio não aceito. Use webm, ogg, m4a, mp3 ou wav.")

    settings = servicos.settings
    pasta = settings.pasta_audio_temp
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    apagar_audios_antigos(pasta)
    caminho = pasta / f"{PREFIXO_AUDIO}{secrets.token_hex(16)}{extensao}"
    try:
        total = 0
        with caminho.open("wb") as destino:
            while bloco := audio.file.read(1024 * 1024):
                total += len(bloco)
                if total > settings.tamanho_maximo_bytes:
                    raise HTTPException(413, _mensagem_tamanho(settings.tamanho_maximo_bytes))
                destino.write(bloco)
        if total == 0:
            raise HTTPException(422, "A gravação chegou vazia. Grave de novo.")
        servicos.repositorio.atualizar_sessao(sessao_id, status="processando_audio", progresso=5, mensagem_erro=None)
        tarefas.add_task(_processador(request).processar_audio, sessao_id, caminho)
    except BaseException:
        apagar_audio(caminho)
        raise
    return _recarregar(servicos, sessao_id)


@rotas.put("/sessoes/{sessao_id}/transcricao", response_model=Sessao)
def editar_transcricao(sessao_id: str, corpo: TranscricaoEditar, servicos: ServicosDep, usuario: UsuarioDep) -> Sessao:
    sessao = _sessao_do_dono(servicos, sessao_id, usuario)
    if sessao.status != "aguardando_queixa":
        raise HTTPException(409, "A transcrição só pode ser corrigida antes de confirmar a queixa.")
    falas = [Fala(papel=f.papel, texto=f.texto.strip()) for f in corpo.falas if f.texto.strip()]
    if not falas:
        raise HTTPException(422, "A transcrição não pode ficar vazia.")
    servicos.repositorio.salvar_transcricao(sessao_id, falas, editada=True)
    return _recarregar(servicos, sessao_id)


@rotas.post("/sessoes/{sessao_id}/queixa", response_model=Sessao)
def confirmar_queixa(
    sessao_id: str,
    corpo: QueixaConfirmar,
    request: Request,
    tarefas: BackgroundTasks,
    servicos: ServicosDep,
    usuario: UsuarioDep,
) -> Sessao:
    sessao = _sessao_do_dono(servicos, sessao_id, usuario)
    primeira_vez = sessao.status == "aguardando_queixa"
    nova_tentativa = sessao.status == "erro" and bool(sessao.falas) and not sessao.hipoteses_aluno
    if not (primeira_vez or nova_tentativa):
        raise HTTPException(409, "A queixa é confirmada logo depois da transcrição.")

    validas = servicos.conteudo.ids_queixas | {QUEIXA_OUTRA}
    queixas: list[str] = []
    for queixa_id in corpo.queixas:
        if queixa_id not in validas:
            raise HTTPException(422, "Escolha uma queixa da lista ou 'outra'.")
        if queixa_id not in queixas:
            queixas.append(queixa_id)

    descricao = None
    if QUEIXA_OUTRA in queixas:
        if len(queixas) > 1:
            raise HTTPException(422, "'Outra' vale sozinha. Escolha queixas da lista ou só 'outra'.")
        descricao = (corpo.descricao_outra or sessao.descricao_outra or "").strip() or None
        if descricao is None:
            raise HTTPException(422, "Escreva em poucas palavras qual foi a queixa.")
        if QUEIXA_OUTRA not in sessao.queixas_confirmadas:
            # Entra na fila uma vez por sessão, inclusive quando a confirmação vem numa nova tentativa.
            servicos.repositorio.registrar_queixa_outra(descricao)

    # Sem o campo no pedido, fica o sexo detectado na conversa; null é "não sei".
    sexo = corpo.sexo_paciente if "sexo_paciente" in corpo.model_fields_set else sessao.sexo_paciente
    servicos.repositorio.atualizar_sessao(
        sessao_id,
        queixas_confirmadas=queixas,
        descricao_outra=descricao,
        sexo_paciente=sexo,
        status="corrigindo",
        progresso=5,
        mensagem_erro=None,
    )
    tarefas.add_task(_processador(request).processar_queixa, sessao_id)
    return _recarregar(servicos, sessao_id)


@rotas.post("/sessoes/{sessao_id}/hipoteses", response_model=Sessao)
def enviar_hipoteses(
    sessao_id: str,
    corpo: HipotesesAluno,
    request: Request,
    tarefas: BackgroundTasks,
    servicos: ServicosDep,
    usuario: UsuarioDep,
) -> Sessao:
    sessao = _sessao_do_dono(servicos, sessao_id, usuario)
    primeira_vez = sessao.status == "aguardando_hipoteses"
    nova_tentativa = sessao.status == "erro" and bool(sessao.hipoteses_aluno) and bool(sessao.avaliacoes)
    if not (primeira_vez or nova_tentativa):
        raise HTTPException(409, "As hipóteses entram depois da correção ficar pronta.")
    hipoteses = [h.strip() for h in corpo.hipoteses if h.strip()]
    if not hipoteses:
        raise HTTPException(422, "Escreva pelo menos uma hipótese.")

    campos = {"status": "gerando_sugestoes", "progresso": 5, "mensagem_erro": None}
    if primeira_vez:
        # Numa nova tentativa o aluno já viu a correção: as hipóteses dele ficam as primeiras.
        campos["hipoteses_aluno"] = hipoteses
    servicos.repositorio.atualizar_sessao(sessao_id, **campos)
    tarefas.add_task(_processador(request).processar_hipoteses, sessao_id)
    return _recarregar(servicos, sessao_id)


@rotas.post("/sessoes/{sessao_id}/contestacoes", response_model=Sessao)
def contestar_item(sessao_id: str, corpo: ContestacaoCriar, servicos: ServicosDep, usuario: UsuarioDep) -> Sessao:
    sessao = _sessao_do_dono(servicos, sessao_id, usuario)
    if not correcao_liberada(sessao) or not sessao.avaliacoes:
        raise HTTPException(409, "Escreva suas hipóteses antes de ver e contestar a correção.")
    avaliacao = next((a for a in sessao.avaliacoes if a.item_id == corpo.item_id), None)
    item = item_do_checklist(servicos.conteudo, avaliacao.checklist_id, corpo.item_id) if avaliacao else None
    try:
        resultado = contestar(
            sessao.avaliacoes,
            sessao.falas,
            corpo,
            sessao.checklists_usados,
            servicos.conteudo.tipos_checklists(),
            sessao.notas,
            item=item,
            llm=servicos.llm,
        )
    except ErroContestacao as erro:
        raise HTTPException(erro.codigo, erro.mensagem) from None
    servicos.repositorio.salvar_avaliacoes(sessao_id, resultado.avaliacoes)
    servicos.repositorio.atualizar_sessao(sessao_id, notas=resultado.notas)
    return _recarregar(servicos, sessao_id)


# ---------- app ----------


def _mensagem_validacao(erro: RequestValidationError) -> str:
    campos = []
    for problema in erro.errors():
        local = [str(p) for p in problema.get("loc", ()) if p not in ("body", "query", "path")]
        if local and local[0] not in campos:
            campos.append(local[0])
    if campos:
        return f"Alguns dados vieram incompletos ou em formato errado. Confira: {', '.join(campos)}."
    return "Alguns dados vieram incompletos ou em formato errado. Confira e tente de novo."


def criar_app(
    settings: Settings | None = None,
    *,
    llm: ClienteLLM | None = None,
    transcritor: Transcritor | None = None,
    repositorio: Repositorio | None = None,
    voz: VozPaciente | None = None,
) -> FastAPI:
    settings = settings or obter_settings()
    servicos = montar_servicos(settings, llm=llm, transcritor=transcritor, repositorio=repositorio, voz=voz)

    @asynccontextmanager
    async def ciclo(_: FastAPI):
        try:
            _ = servicos.conteudo  # valida content/ na subida
        except ErroConteudo as erro:
            logger.error("conteúdo inválido: %s", erro)
            raise
        preparar_pasta_audio(settings.pasta_audio_temp)
        yield

    app = FastAPI(title="AnamneLab", version="0.1.0", lifespan=ciclo)
    app.state.servicos = servicos
    app.state.processador = Processador(servicos)

    @app.exception_handler(RequestValidationError)
    async def _validacao(_: Request, erro: RequestValidationError) -> JSONResponse:
        return JSONResponse({"detail": _mensagem_validacao(erro)}, status_code=422)

    @app.exception_handler(ErroConteudo)
    async def _conteudo(_: Request, erro: ErroConteudo) -> JSONResponse:
        logger.error("conteúdo inválido: %s", erro)
        return JSONResponse(
            {"detail": "O conteúdo do app está com problema. Avise quem cuida do AnamneLab."},
            status_code=503,
        )

    app.include_router(rotas)
    # O último adicionado fica por fora: CORS envolve tudo, inclusive as respostas de erro.
    app.add_middleware(ProtegerErros)
    app.add_middleware(LimiteAudio, limite_bytes=settings.tamanho_maximo_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.lista_cors,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


app = criar_app()
