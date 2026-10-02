import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { Navigate, useParams } from "react-router-dom";
import { api, textoDoErro } from "../api/cliente";
import { Aviso } from "../componentes/Aviso";
import { Avatar } from "../componentes/Avatar";
import { Folha } from "../componentes/Folha";
import type { Consentimento, Termo as TipoTermo } from "../api/tipos";
import {
  IconeAviso,
  IconeBalao,
  IconeEnviar,
  IconeLampada,
  IconeMicrofone,
  IconeSelo,
  IconeSemSom,
  IconeSom,
} from "../componentes/Icones";
import { Carregando, Tela } from "../componentes/Tela";
import { rotaDaSessao, useQueixas, useSessao } from "../util/sessao";
import { useNavegar, vibrar } from "../util/movimento";
import { aceitarComoDono, useAceiteDono } from "../util/aceites";
import { usePerfil } from "../util/perfil";
import { salvarPreferencias, usePreferencias } from "../util/preferencias";
import { destravarSom, falarPaciente, pararVoz } from "../util/vozPaciente";
import { FolhaAceite } from "./Termo";

/** Igual a MAXIMO_PERGUNTA no backend. */
const LIMITE_PERGUNTA = 1000;

/** Uma pergunta falada passa disso só por engano (botão preso). */
const FALA_MAXIMA_S = 60;
/** Toque mais curto que isso liga o microfone até o próximo toque, em vez de segurar. */
const TOQUE_CURTO_MS = 350;
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
  if (nome === "NotAllowedError" || nome === "SecurityError") {
    return "O app não tem permissão para usar o microfone. Libere o microfone para este site nas configurações do navegador.";
  }
  if (nome === "NotFoundError" || nome === "OverconstrainedError") {
    return "Não encontramos um microfone neste aparelho. Escreva a pergunta.";
  }
  return "Não deu para ligar o microfone. Tente de novo ou escreva a pergunta.";
}

type Microfone = "parado" | "ligando" | "segurando" | "tocado";

const PONTOS = [
  { icone: <IconeBalao />, texto: "Você faz o médico e fala ou escreve as perguntas. A IA responde como o paciente." },
  { icone: <IconeLampada />, texto: "Ela só conta o que você perguntar, do jeito de quem não é da saúde." },
  { icone: <IconeSom />, texto: "O paciente responde em voz alta. Dá para desligar a voz na consulta." },
  { icone: <IconeSelo />, texto: "No fim, a correção é a mesma da gravação, item a item." },
];

/** Escolha do caso: uma queixa da biblioteca ou qualquer uma, sorteada. */
export function NovoPacienteIA() {
  const navegar = useNavegar();
  const { queixas } = useQueixas();
  const [queixa, setQueixa] = useState("");
  const [chamando, setChamando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const chamar = async () => {
    setChamando(true);
    setErro(null);
    try {
      const cartao = queixa ? await api.sortearCartao(queixa) : null;
      const sessao = await api.criarSessao({ origem_caso: "paciente_ia", cartao_id: cartao?.id ?? null });
      vibrar(10);
      navegar(rotaDaSessao(sessao), { replace: true });
    } catch (e) {
      setErro(textoDoErro(e));
      setChamando(false);
    }
  };

  return (
    <Tela
      titulo="Paciente pela IA"
      subtitulo="Treine sozinho, quando quiser, com um paciente simulado."
      voltar="/"
      rodape={
        <button
          className={`al-botao al-botao-principal app-botao-largo${chamando ? " is-enviando" : ""}`}
          type="button"
          onClick={() => void chamar()}
          disabled={chamando}
        >
          {chamando ? "Chamando o paciente…" : "Chamar o paciente"}
        </button>
      }
    >
      <ul className="app-topicos">
        {PONTOS.map((p) => (
          <li key={p.texto}>
            {p.icone}
            <span>{p.texto}</span>
          </li>
        ))}
      </ul>
      <label className="app-campo">
        <span className="app-campo-rotulo">Queixa do caso</span>
        <select value={queixa} onChange={(e) => setQueixa(e.target.value)}>
          <option value="">Surpresa (qualquer queixa)</option>
          {queixas.map((q) => (
            <option key={q.id} value={q.id}>
              {q.nome}
            </option>
          ))}
        </select>
      </label>
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <p className="app-legenda">
        As perguntas vão para o serviço de IA configurado no app. Não escreva dados de pessoas reais.
      </p>
    </Tela>
  );
}

/** A consulta: perguntas à direita, respostas do paciente à esquerda. Fala ou teclado. */
export function Conversa() {
  const { id } = useParams();
  const navegar = useNavegar();
  const { sessao, erro: erroSessao, definir } = useSessao(id);
  const perfil = usePerfil();
  const aceiteDono = useAceiteDono();
  const { vozPaciente } = usePreferencias();
  const [texto, setTexto] = useState("");
  const [esperando, setEsperando] = useState<string | null>(null);
  const [ouvindo, setOuvindo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [confirmar, setConfirmar] = useState(false);
  const [encerrando, setEncerrando] = useState(false);
  const [microfone, setMicrofone] = useState<Microfone>("parado");
  const [segundos, setSegundos] = useState(0);
  const [falando, setFalando] = useState<number | null>(null);
  const [vozesPiper, setVozesPiper] = useState<("feminino" | "masculino")[]>([]);
  const [termo, setTermo] = useState<TipoTermo | null>(null);
  const [pedirAceite, setPedirAceite] = useState(false);
  const fim = useRef<HTMLDivElement>(null);
  const campo = useRef<HTMLTextAreaElement>(null);
  const fluxo = useRef<MediaStream | null>(null);
  const gravador = useRef<MediaRecorder | null>(null);
  const pedacos = useRef<Blob[]>([]);
  const inicio = useRef(0);
  const relogio = useRef<number | undefined>(undefined);
  const enviarAoParar = useRef(true);
  const pararAoLigar = useRef(false);
  const toqueInicio = useRef(0);

  const falas = sessao?.falas ?? [];
  const perguntas = falas.filter((f) => f.papel === "entrevistador").length;
  const tamanho = texto.trim().length;
  const passou = tamanho > LIMITE_PERGUNTA;
  const gravando = microfone === "segurando" || microfone === "tocado";
  const ocupado = Boolean(esperando) || ouvindo;

  useEffect(() => {
    fim.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [falas.length, esperando, ouvindo]);

  useEffect(() => {
    let ativo = true;
    api.saude().then(
      (s) => ativo && setVozesPiper(s.vozes_paciente ?? []),
      () => undefined,
    );
    api.termo().then(
      (t) => ativo && setTermo(t),
      () => undefined,
    );
    return () => {
      ativo = false;
    };
  }, []);

  const soltarMicrofone = useCallback(() => {
    window.clearInterval(relogio.current);
    fluxo.current?.getTracks().forEach((t) => t.stop());
    fluxo.current = null;
  }, []);

  // Ao sair da consulta: microfone desligado e paciente calado.
  useEffect(
    () => () => {
      enviarAoParar.current = false;
      if (gravador.current?.state === "recording") gravador.current.stop();
      soltarMicrofone();
      pararVoz();
    },
    [soltarMicrofone],
  );

  const sexo = sessao?.sexo_paciente ?? "feminino";

  const ouvirFala = useCallback(
    async (indice: number, textoFala: string) => {
      if (!id) return;
      setFalando(indice);
      const falou = await falarPaciente({ sessaoId: id, indice, texto: textoFala, sexo, piper: vozesPiper });
      setFalando((f) => (f === indice ? null : f));
      if (!falou) {
        setAviso(
          "Este aparelho não tem voz em português. No Windows, instale em Configurações, Hora e idioma, Fala. A resposta continua escrita.",
        );
      }
    },
    [id, sexo, vozesPiper],
  );

  /** Depois de cada resposta, o paciente fala a última fala dele (com a voz ligada). */
  const responder = (atualizada: NonNullable<typeof sessao>) => {
    definir(() => atualizada);
    vibrar(6);
    const ultima = atualizada.falas.length - 1;
    const fala = atualizada.falas[ultima];
    if (vozPaciente && fala?.papel === "paciente") void ouvirFala(ultima, fala.texto);
  };

  if (!id) return <Navigate to="/" replace />;
  if (sessao && sessao.status !== "conversando") return <Navigate to={rotaDaSessao(sessao)} replace />;

  const enviar = async () => {
    const pergunta = texto.trim();
    if (!pergunta || ocupado || pergunta.length > LIMITE_PERGUNTA) return;
    destravarSom();
    pararVoz();
    setEsperando(pergunta);
    setTexto("");
    setErro(null);
    try {
      responder(await api.perguntarAoPaciente(id, pergunta));
    } catch (e) {
      setErro(textoDoErro(e));
      setTexto(pergunta); // a pergunta volta para o campo, para tentar de novo
    } finally {
      setEsperando(null);
      campo.current?.focus();
    }
  };

  const enviarFala = async (audio: Blob, mime: string) => {
    setOuvindo(true);
    setErro(null);
    try {
      responder(await api.perguntarFalando(id, audio, `pergunta.${extensao(mime)}`));
    } catch (e) {
      setErro(textoDoErro(e));
    } finally {
      setOuvindo(false);
    }
  };

  /** O aceite do termo vale para a sessão: registra o do dono, se ainda não está nela. */
  const temAceite = (t: TipoTermo) =>
    Boolean(sessao?.consentimentos.some((c) => c.forma === "aceite" && c.versao_termo === t.versao));

  const prepararAceite = async (): Promise<boolean> => {
    if (!termo) {
      setErro("Não deu para carregar o termo de gravação. Tente de novo em instantes.");
      return false;
    }
    if (temAceite(termo)) return true;
    if (aceiteDono?.versao !== termo.versao) {
      setPedirAceite(true);
      return false;
    }
    try {
      const c = await api.registrarConsentimento(id, {
        papel: "medico",
        nome_informado: perfil.nome.trim() || "Quem abriu a sessão",
        versao_termo: termo.versao,
        aceito: true,
      });
      definir((s) => s && { ...s, consentimentos: [...s.consentimentos, c] });
      setAviso("Microfone pronto. Segure o botão enquanto fala e solte para enviar.");
    } catch (e) {
      setErro(textoDoErro(e));
    }
    return false;
  };

  const aceitou = (c: Consentimento) => {
    if (termo) aceitarComoDono(termo.versao);
    definir((s) => s && { ...s, consentimentos: [...s.consentimentos, c] });
    setPedirAceite(false);
    setAviso("Microfone pronto. Segure o botão enquanto fala e solte para enviar.");
  };

  const pararGravacao = (enviarFala_: boolean) => {
    enviarAoParar.current = enviarFala_;
    window.clearInterval(relogio.current);
    if (gravador.current?.state === "recording") gravador.current.stop();
    else if (microfone === "ligando") pararAoLigar.current = true;
  };

  const ligarMicrofone = async (modo: Microfone) => {
    setErro(null);
    setAviso(null);
    pararVoz();
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setErro("Este navegador não grava áudio. Escreva a pergunta ou use o Chrome ou o Safari atualizados.");
      return;
    }
    setMicrofone("ligando");
    pararAoLigar.current = false;
    try {
      fluxo.current ??= await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
    } catch (e) {
      setErro(mensagemMicrofone(e));
      setMicrofone("parado");
      return;
    }
    const formato = escolherFormato();
    let g: MediaRecorder;
    try {
      g = new MediaRecorder(fluxo.current, { ...(formato ? { mimeType: formato } : {}), audioBitsPerSecond: 32_000 });
    } catch {
      soltarMicrofone();
      setErro("Este navegador não conseguiu gravar. Escreva a pergunta.");
      setMicrofone("parado");
      return;
    }
    pedacos.current = [];
    enviarAoParar.current = true;
    g.ondataavailable = (ev) => {
      if (ev.data.size > 0) pedacos.current.push(ev.data);
    };
    g.onstop = () => {
      const mime = g.mimeType || formato || "audio/webm";
      const audio = new Blob(pedacos.current, { type: mime });
      const duracao = (performance.now() - inicio.current) / 1000;
      pedacos.current = [];
      gravador.current = null;
      setMicrofone("parado");
      if (!enviarAoParar.current) return;
      if (audio.size === 0 || duracao < 0.5) {
        setAviso("Não deu tempo de ouvir. Segure o botão enquanto fala e solte no fim da pergunta.");
        return;
      }
      void enviarFala(audio, mime);
    };
    gravador.current = g;
    g.start();
    inicio.current = performance.now();
    setSegundos(0);
    setMicrofone(modo);
    vibrar(10);
    relogio.current = window.setInterval(() => {
      const s = (performance.now() - inicio.current) / 1000;
      setSegundos(s);
      if (s >= FALA_MAXIMA_S) pararGravacao(true);
    }, 250);
    if (pararAoLigar.current) pararGravacao(true);
  };

  // Segurar e soltar envia; um toque curto liga até o próximo toque.
  const aoApertar = async (e: PointerEvent<HTMLButtonElement>) => {
    if (e.button !== 0 || ocupado || !sessao) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    destravarSom();
    if (microfone === "tocado") {
      pararGravacao(true);
      return;
    }
    if (microfone !== "parado") return;
    toqueInicio.current = performance.now();
    if (!(await prepararAceite())) return;
    await ligarMicrofone("segurando");
  };
  const aoSoltar = () => {
    if (microfone !== "segurando" && microfone !== "ligando") return;
    if (performance.now() - toqueInicio.current < TOQUE_CURTO_MS) {
      setMicrofone((m) => (m === "segurando" ? "tocado" : m));
      return;
    }
    pararGravacao(true);
  };
  const aoTeclar = async (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key !== " " && e.key !== "Enter") return;
    e.preventDefault();
    if (e.repeat || ocupado || !sessao) return;
    destravarSom();
    if (gravando) {
      pararGravacao(true);
      return;
    }
    if (await prepararAceite()) await ligarMicrofone("tocado");
  };

  const encerrar = async () => {
    setEncerrando(true);
    setErro(null);
    pararVoz();
    try {
      const atualizada = await api.encerrarConversa(id);
      vibrar([10, 60, 10]);
      navegar(rotaDaSessao(atualizada), { replace: true });
    } catch (e) {
      setErro(textoDoErro(e));
      setEncerrando(false);
      setConfirmar(false);
    }
  };

  const alternarVoz = () => {
    if (vozPaciente) pararVoz();
    salvarPreferencias({ vozPaciente: !vozPaciente });
  };

  return (
    <Tela
      titulo="Consulta"
      sobretitulo="Paciente pela IA"
      voltar="/"
      rotuloVoltar="Voltar ao início (a consulta fica salva)"
      className="app-tela-conversa"
      canto={
        <button
          className="al-botao al-botao-texto"
          type="button"
          onClick={() => setConfirmar(true)}
          disabled={!sessao || perguntas === 0 || ocupado || gravando}
        >
          Encerrar
        </button>
      }
      rodape={
        <form
          className="app-perguntar"
          onSubmit={(e) => {
            e.preventDefault();
            void enviar();
          }}
        >
          {tamanho > LIMITE_PERGUNTA * 0.8 && !gravando && (
            <p id="tamanho-pergunta" className={`app-perguntar-conta${passou ? " is-passou" : ""}`} aria-live="polite">
              {passou
                ? `Pergunta longa demais: ${tamanho} de ${LIMITE_PERGUNTA} caracteres. Divida em duas.`
                : `${tamanho} de ${LIMITE_PERGUNTA} caracteres`}
            </p>
          )}
          <button
            className={`al-botao app-botao-icone app-botao-falar${gravando ? " is-gravando" : ""}`}
            type="button"
            aria-label={gravando ? "Parar e enviar a pergunta" : "Segure para falar a pergunta"}
            aria-pressed={gravando}
            disabled={!sessao || ocupado}
            onPointerDown={(e) => void aoApertar(e)}
            onPointerUp={aoSoltar}
            onPointerCancel={() => microfone === "segurando" && pararGravacao(false)}
            onKeyDown={(e) => void aoTeclar(e)}
            onContextMenu={(e) => e.preventDefault()}
          >
            <IconeMicrofone />
          </button>
          {gravando || microfone === "ligando" ? (
            <p className="app-perguntar-gravando" aria-live="polite">
              <span className="al-ponto" aria-hidden="true" />
              {microfone === "tocado" ? "Ouvindo. Toque no microfone para enviar." : "Ouvindo. Solte para enviar."}
              <span className="app-tabular">{Math.floor(segundos)}s</span>
            </p>
          ) : (
            <textarea
              ref={campo}
              rows={1}
              placeholder="Escreva a pergunta"
              aria-label="Pergunta ao paciente"
              aria-invalid={passou || undefined}
              aria-describedby={tamanho > LIMITE_PERGUNTA * 0.8 ? "tamanho-pergunta" : undefined}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void enviar();
                }
              }}
              disabled={!sessao}
            />
          )}
          {!gravando && microfone !== "ligando" && (
            <button
              className="al-botao al-botao-principal app-botao-icone"
              type="submit"
              aria-label="Enviar pergunta"
              disabled={!tamanho || passou || ocupado || !sessao}
            >
              <IconeEnviar />
            </button>
          )}
        </form>
      }
    >
      {erroSessao && <Aviso tipo="erro">{erroSessao}</Aviso>}
      {!sessao && !erroSessao && <Carregando texto="Chamando o paciente…" />}

      {sessao && (
        <div className="app-chat" aria-live="polite">
          <p className="app-dica">
            <IconeAviso />O paciente chegou e está sentado à sua frente. Comece como numa consulta de verdade.
          </p>
          <button className="al-botao al-botao-texto app-alternar-voz" type="button" onClick={alternarVoz}>
            {vozPaciente ? <IconeSom /> : <IconeSemSom />}
            {vozPaciente ? "Voz do paciente ligada" : "Voz do paciente desligada"}
          </button>
          {falas.map((f, i) =>
            f.papel === "entrevistador" ? (
              <p key={i} className="app-bolha app-bolha-medico">
                {f.texto}
              </p>
            ) : (
              <div key={i} className="app-bolha-linha">
                <Avatar nome="Paciente" papel="paciente" tamanho={28} avatar="" />
                <p className={`app-bolha app-bolha-paciente${falando === i ? " is-falando" : ""}`}>{f.texto}</p>
                {vozPaciente && (
                  <button
                    className="al-botao al-botao-texto app-ouvir"
                    type="button"
                    aria-label={falando === i ? "Parar a voz" : "Ouvir de novo"}
                    onClick={() => {
                      destravarSom();
                      if (falando === i) {
                        pararVoz();
                        setFalando(null);
                      } else void ouvirFala(i, f.texto);
                    }}
                  >
                    {falando === i ? <IconeSemSom /> : <IconeSom />}
                  </button>
                )}
              </div>
            ),
          )}
          {(esperando || ouvindo) && (
            <>
              <p className={`app-bolha app-bolha-medico is-enviando${ouvindo ? " is-transcrevendo" : ""}`}>
                {esperando ?? "Transcrevendo a sua pergunta…"}
              </p>
              <div className="app-bolha-linha">
                <Avatar nome="Paciente" papel="paciente" tamanho={28} avatar="" />
                <p className="app-bolha app-bolha-paciente app-digitando" aria-label="O paciente está respondendo">
                  <span />
                  <span />
                  <span />
                </p>
              </div>
            </>
          )}
          {aviso && <Aviso tipo="info">{aviso}</Aviso>}
          {erro && <Aviso tipo="erro">{erro}</Aviso>}
          <div ref={fim} />
        </div>
      )}

      {pedirAceite && termo && (
        <FolhaAceite
          papel="medico"
          nome={perfil.nome.trim() || "Quem abriu a sessão"}
          termo={termo}
          sessaoId={id}
          onRegistrado={aceitou}
          onFechar={() => setPedirAceite(false)}
        />
      )}

      {confirmar && (
        <Folha
          titulo="Encerrar a consulta?"
          subtitulo={`Você fez ${perguntas} ${perguntas === 1 ? "pergunta" : "perguntas"}. Depois de encerrar, não dá para perguntar mais.`}
          onFechar={() => setConfirmar(false)}
        >
          <div className="app-grupo">
            <button
              className="al-botao al-botao-principal app-botao-largo"
              type="button"
              onClick={() => void encerrar()}
              disabled={encerrando}
            >
              {encerrando ? "Encerrando…" : "Encerrar e ver a correção"}
            </button>
            <button
              className="al-botao al-botao-texto app-botao-largo"
              type="button"
              onClick={() => setConfirmar(false)}
            >
              Continuar a consulta
            </button>
          </div>
        </Folha>
      )}
    </Tela>
  );
}
