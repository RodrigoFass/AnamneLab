import { useCallback, useEffect, useRef, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import { api, textoDoErro } from "../api/cliente";
import { Aviso } from "../componentes/Aviso";
import { BotaoGravar } from "../componentes/BotaoGravar";
import { Contador } from "../componentes/Contador";
import { IconeAviso } from "../componentes/Icones";
import { Onda } from "../componentes/Onda";
import { Carregando, Tela } from "../componentes/Tela";
import { formatarTempo } from "../util/formato";
import { linhaDaDupla } from "../util/nomes";
import { rotaDaSessao, useSessao } from "../util/sessao";
import { useNavegar } from "../util/movimento";

/** 20 minutos. */
const DURACAO_MAXIMA_S = 20 * 60;
/** 25 MB, o limite do backend e da transcrição. */
const TAMANHO_MAXIMO = 25 * 1024 * 1024;
/** 32 kbit/s mono: 20 min ficam perto de 5 MB, com folga para os 25 MB. */
const TAXA_AUDIO = 32_000;

const FORMATOS = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];

function escolherFormato(): string | undefined {
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return undefined;
  return FORMATOS.find((f) => MediaRecorder.isTypeSupported(f));
}

function extensao(mime: string): string {
  if (mime.includes("mp4") || mime.includes("aac")) return "m4a";
  if (mime.includes("ogg")) return "ogg";
  return "webm";
}

function mensagemMicrofone(e: unknown): string {
  const nome = e instanceof DOMException ? e.name : "";
  switch (nome) {
    case "NotAllowedError":
    case "SecurityError":
      return "O app não tem permissão para usar o microfone. Libere o microfone para este site nas configurações do navegador e toque para gravar de novo.";
    case "NotFoundError":
    case "OverconstrainedError":
      return "Não encontramos um microfone neste aparelho. Confira se ele está ligado e tente de novo.";
    case "NotReadableError":
    case "AbortError":
      return "O microfone está ocupado por outro app. Feche chamadas ou gravadores abertos e tente de novo.";
    default:
      return "Não deu para ligar o microfone. Tente de novo; se continuar, reinicie o navegador.";
  }
}

type Fase = "pronto" | "gravando" | "parado" | "enviando";

interface Gravacao {
  blob: Blob;
  segundos: number;
  mime: string;
}

export function Gravar() {
  const { id } = useParams();
  const navegar = useNavegar();
  const { sessao, erro: erroSessao } = useSessao(id);

  const [fase, setFase] = useState<Fase>("pronto");
  const [segundos, setSegundos] = useState(0);
  const [gravacao, setGravacao] = useState<Gravacao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  /** O mesmo fluxo do microfone, em estado, para a onda desenhar o volume. */
  const [fluxoAtivo, setFluxoAtivo] = useState<MediaStream | null>(null);

  const gravador = useRef<MediaRecorder | null>(null);
  const fluxo = useRef<MediaStream | null>(null);
  const pedacos = useRef<Blob[]>([]);
  const relogio = useRef<number | null>(null);
  const inicio = useRef(0);
  const cancelado = useRef(false);
  const travaTela = useRef<WakeLockSentinel | null>(null);

  const soltarRecursos = useCallback(() => {
    if (relogio.current !== null) {
      window.clearInterval(relogio.current);
      relogio.current = null;
    }
    fluxo.current?.getTracks().forEach((t) => t.stop());
    fluxo.current = null;
    setFluxoAtivo(null);
    void travaTela.current?.release().catch(() => undefined);
    travaTela.current = null;
  }, []);

  const parar = useCallback(
    (automatico: boolean) => {
      cancelado.current = true;
      if (relogio.current !== null) {
        window.clearInterval(relogio.current);
        relogio.current = null;
      }
      const g = gravador.current;
      if (g && g.state !== "inactive") {
        g.stop(); // onstop monta a gravação e solta o microfone
      } else {
        soltarRecursos();
        setFase("pronto");
      }
      if (automatico) {
        setAviso("A gravação chegou a 20 minutos e parou sozinha. Envie o que foi gravado.");
      }
    },
    [soltarRecursos],
  );

  const iniciar = useCallback(async () => {
    // Muda o estado no toque; o microfone liga logo depois.
    setFase("gravando");
    setSegundos(0);
    setErro(null);
    setAviso(null);
    setGravacao(null);
    cancelado.current = false;

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setErro("Este navegador não grava áudio. Use o Chrome ou o Safari atualizados.");
      setFase("pronto");
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
    } catch (e) {
      setErro(mensagemMicrofone(e));
      setFase("pronto");
      return;
    }
    if (cancelado.current) {
      stream.getTracks().forEach((t) => t.stop());
      return;
    }
    fluxo.current = stream;
    setFluxoAtivo(stream);

    const formato = escolherFormato();
    let g: MediaRecorder;
    try {
      g = new MediaRecorder(stream, {
        ...(formato ? { mimeType: formato } : {}),
        audioBitsPerSecond: TAXA_AUDIO,
      });
    } catch {
      soltarRecursos();
      setErro("Este navegador não conseguiu iniciar a gravação. Use o Chrome ou o Safari atualizados.");
      setFase("pronto");
      return;
    }

    pedacos.current = [];
    g.ondataavailable = (ev) => {
      if (ev.data.size > 0) pedacos.current.push(ev.data);
    };
    g.onstop = () => {
      const mime = g.mimeType || formato || "audio/webm";
      const blob = new Blob(pedacos.current, { type: mime });
      pedacos.current = [];
      const total = Math.min(DURACAO_MAXIMA_S, (performance.now() - inicio.current) / 1000);
      soltarRecursos();
      gravador.current = null;
      if (blob.size === 0) {
        setErro("Não deu para ouvir nada. Grave de novo num lugar mais calmo.");
        setFase("pronto");
        return;
      }
      setGravacao({ blob, segundos: total, mime });
      setFase("parado");
    };
    g.onerror = () => {
      setErro("A gravação foi interrompida. Grave de novo num lugar mais calmo.");
      parar(false);
    };

    gravador.current = g;
    g.start(1000);
    inicio.current = performance.now();
    relogio.current = window.setInterval(() => {
      const s = (performance.now() - inicio.current) / 1000;
      setSegundos(s);
      if (s >= DURACAO_MAXIMA_S) parar(true);
    }, 250);

    // Mantém a tela acesa: em vários celulares, a tela apagada para o microfone.
    try {
      travaTela.current = (await navigator.wakeLock?.request("screen")) ?? null;
    } catch {
      travaTela.current = null;
    }
  }, [parar, soltarRecursos]);

  useEffect(
    () => () => {
      cancelado.current = true;
      const g = gravador.current;
      if (g && g.state !== "inactive") {
        g.onstop = null;
        g.stop();
      }
      gravador.current = null;
      soltarRecursos();
    },
    [soltarRecursos],
  );

  const alternar = () => {
    if (fase === "gravando") parar(false);
    else if (fase === "pronto") void iniciar();
  };

  const enviar = async () => {
    if (!gravacao || !id) return;
    if (gravacao.blob.size > TAMANHO_MAXIMO) {
      setErro("A gravação passou de 25 MB e não pode ser enviada. Grave de novo, em até 20 minutos.");
      return;
    }
    setFase("enviando");
    setErro(null);
    try {
      await api.enviarAudio(id, gravacao.blob, `gravacao.${extensao(gravacao.mime)}`);
      setGravacao(null);
      navegar(`/sessao/${id}/processando`, { replace: true });
    } catch (e) {
      setErro(textoDoErro(e));
      setFase("parado");
    }
  };

  const descartar = () => {
    setGravacao(null);
    setSegundos(0);
    setAviso(null);
    setErro(null);
    setFase("pronto");
  };

  if (!id) return <Navigate to="/" replace />;
  if (sessao) {
    const destino = rotaDaSessao(sessao);
    if (fase !== "enviando" && destino !== `/sessao/${id}/gravar`) return <Navigate to={destino} replace />;
  }

  const estadoBotao = fase === "gravando" ? "gravando" : fase === "enviando" ? "processando" : "pronto";
  const titulo =
    fase === "gravando" ? "Gravando" : fase === "pronto" ? "Pronto para gravar" : "Gravação concluída";
  const colega = sessao?.consentimentos.find((c) => c.forma === "declarado_pelo_dono")?.nome_informado;
  const tempo = fase === "parado" || fase === "enviando" ? (gravacao?.segundos ?? segundos) : segundos;

  return (
    <Tela
      titulo={titulo}
      sobretitulo={sessao ? linhaDaDupla(sessao.consentimentos, sessao.origem_caso) : undefined}
      voltar={fase === "gravando" ? undefined : "/"}
      rotuloVoltar="Voltar ao início"
      className="app-tela-gravar"
      chaveTitulo={titulo}
    >
      {erroSessao && <Aviso tipo="erro">{erroSessao}</Aviso>}
      {!sessao && !erroSessao && <Carregando />}

      {sessao && (
        <>
          <p className={`app-cronometro app-tabular${fase === "gravando" ? " is-gravando" : ""}`} aria-hidden="true">
            <Contador texto={formatarTempo(tempo)} />
          </p>
          <Onda fluxo={fase === "gravando" ? fluxoAtivo : null} />

          <p className="app-dica">
            <IconeAviso />
            {fase === "parado"
              ? "O áudio é apagado logo depois da transcrição."
              : fase === "pronto" && colega
                ? `Avise ${colega} que a conversa vai ser gravada. Celular entre os dois, num lugar calmo.`
                : "Celular entre os dois, num lugar calmo. Use só casos simulados."}
          </p>
          {fase === "pronto" && (
            <p className="app-legenda app-centro">A gravação vai até 20 minutos e para sozinha.</p>
          )}

          {aviso && <Aviso titulo="Gravação encerrada">{aviso}</Aviso>}
          {erro && <Aviso tipo="erro">{erro}</Aviso>}

          <div className="app-gravar-area">
            {fase === "parado" && gravacao ? (
              <div className="app-gravado app-surge">
                <button className="al-botao al-botao-principal app-botao-largo" type="button" onClick={() => void enviar()}>
                  Enviar para correção
                </button>
                <button className="al-botao al-botao-texto app-botao-largo" type="button" onClick={descartar}>
                  Gravar de novo
                </button>
              </div>
            ) : (
              <BotaoGravar
                estado={estadoBotao}
                segundos={segundos}
                legendaProcessando="Enviando para correção"
                onAlternar={alternar}
              />
            )}
          </div>
        </>
      )}
    </Tela>
  );
}
