import { useCallback, useEffect, useRef, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import { api, ErroApi, textoDoErro } from "../api/cliente";
import type { Consentimento, Sessao, Sexo, Termo as TipoTermo } from "../api/tipos";
import { Aviso } from "../componentes/Aviso";
import { Folha } from "../componentes/Folha";
import { IconeBalao, IconeEnviar, IconeMicrofone, IconeMicrofoneMudo, IconeSelo, IconeX } from "../componentes/Icones";
import { Carregando, Tela } from "../componentes/Tela";
import { aceitarComoDono, useAceiteDono } from "../util/aceites";
import { Escuta } from "../util/escuta";
import { useNavegar, vibrar } from "../util/movimento";
import { usePerfil } from "../util/perfil";
import { rotaDaSessao, useSessao } from "../util/sessao";
import { destravarSom, falarPaciente, pararVoz } from "../util/vozPaciente";
import { FolhaAceite } from "./Termo";
import { Guia, resumoDaConsulta } from "../componentes/Guia";

/** Igual a MAXIMO_PERGUNTA no backend. */
const LIMITE_PERGUNTA = 1000;

type Estado = "inicio" | "ouvindo" | "aluno" | "pensando" | "paciente";

const LEGENDA: Record<Estado, string> = {
  inicio: "Toque em começar quando estiver pronto.",
  ouvindo: "Pode falar.",
  aluno: "Ouvindo…",
  pensando: "O paciente está pensando…",
  paciente: "O paciente está falando.",
};

function mensagemMicrofone(e: unknown): string {
  const nome = e instanceof DOMException ? e.name : "";
  if (nome === "NotAllowedError" || nome === "SecurityError") {
    return "O app não tem permissão para usar o microfone. Libere o microfone para este site nas configurações do navegador.";
  }
  if (nome === "NotFoundError" || nome === "OverconstrainedError") {
    return "Não encontramos um microfone neste aparelho. Use a conversa por chat.";
  }
  return "Não deu para ligar o microfone. Tente de novo ou use a conversa por chat.";
}

/** Duas gotas encaixadas: petróleo é o médico (aluno) e mostarda, o paciente. A cauda some aos poucos. */
function Gotas() {
  // Meia gota de um círculo de raio 100: a cabeça é o círculo de raio 50 embaixo, a cauda sobe pela borda.
  const gota = "M0,-100 A100,100 0 0,0 0,100 A50,50 0 0,0 0,0 A50,50 0 0,1 0,-100 Z";
  return (
    <svg className="app-gotas" viewBox="-130 -130 260 260" aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id="gota-medico" gradientUnits="userSpaceOnUse" cx="-20" cy="50" r="125">
          <stop offset="0" stopColor="var(--petroleo)" />
          <stop offset="0.5" stopColor="var(--petroleo)" />
          <stop offset="1" stopColor="var(--petroleo)" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="gota-paciente" gradientUnits="userSpaceOnUse" cx="-20" cy="50" r="125">
          <stop offset="0" stopColor="var(--mostarda)" />
          <stop offset="0.5" stopColor="var(--mostarda)" />
          <stop offset="1" stopColor="var(--mostarda)" stopOpacity="0" />
        </radialGradient>
        <filter id="gota-borda" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="3" />
        </filter>
      </defs>
      <g className="app-gota app-gota-medico">
        <path d={gota} transform="translate(-6 4) scale(0.9)" fill="url(#gota-medico)" filter="url(#gota-borda)" />
      </g>
      <g className="app-gota app-gota-paciente">
        <path
          d={gota}
          transform="rotate(180) translate(-6 4) scale(0.9)"
          fill="url(#gota-paciente)"
          filter="url(#gota-borda)"
        />
      </g>
    </svg>
  );
}

/** Consulta por voz, sem botão: o app percebe quando o aluno fala e o paciente responde falando. */
export function ConversaVoz() {
  const { id } = useParams();
  const navegar = useNavegar();
  const { sessao, erro: erroSessao, definir } = useSessao(id);
  const perfil = usePerfil();
  const aceiteDono = useAceiteDono();
  const [estado, setEstado] = useState<Estado>("inicio");
  const [mudo, setMudo] = useState(false);
  const [texto, setTexto] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [termo, setTermo] = useState<TipoTermo | null>(null);
  const [vozesPiper, setVozesPiper] = useState<Sexo[]>([]);
  const [pedirAceite, setPedirAceite] = useState(false);
  const [confirmar, setConfirmar] = useState(false);
  const [encerrando, setEncerrando] = useState(false);
  const [despediu, setDespediu] = useState(false);
  const [notaGuia, setNotaGuia] = useState<string | null>(null);
  const [horaDoExame, setHoraDoExame] = useState(false);
  const esfera = useRef<HTMLDivElement>(null);
  const escuta = useRef<Escuta | null>(null);
  const ativo = useRef(true);
  // As funções da escuta rodam fora do React; estas refs trazem os valores atuais.
  const atual = useRef({ vozesPiper, sexo: "feminino" as Sexo });
  atual.current = { vozesPiper, sexo: sessao?.sexo_paciente ?? "feminino" };
  // Quantas notas do guia já estavam na consulta: só a nota nova aparece na tela.
  const notasVistas = useRef<number | null>(null);
  if (sessao && notasVistas.current === null) notasVistas.current = sessao.consulta_ia?.notas_guia.length ?? 0;

  useEffect(() => {
    ativo.current = true;
    api.saude().then(
      (s) => ativo.current && setVozesPiper(s.vozes_paciente ?? []),
      () => undefined,
    );
    api.termo().then(
      (t) => ativo.current && setTermo(t),
      () => undefined,
    );
    return () => {
      ativo.current = false;
      escuta.current?.parar();
      escuta.current = null;
      pararVoz();
    };
  }, []);

  /** Depois da resposta: o paciente fala a última fala dele e a escuta volta. */
  const responder = useCallback(
    async (atualizada: Sessao) => {
      if (!ativo.current) return;
      const notasAntes = notasVistas.current ?? 0;
      definir(() => atualizada);
      vibrar(6);
      const notas = atualizada.consulta_ia?.notas_guia ?? [];
      notasVistas.current = notas.length;
      setNotaGuia(notas.length > notasAntes ? (notas[notas.length - 1]?.texto ?? null) : null);
      const ultima = atualizada.falas.length - 1;
      const fala = atualizada.falas[ultima];
      if (fala?.papel === "paciente") {
        setEstado("paciente");
        const { vozesPiper: piper, sexo } = atual.current;
        const falou = await falarPaciente({ sessaoId: atualizada.id, indice: ultima, texto: fala.texto, sexo, piper });
        if (!falou && ativo.current) {
          setAviso("Este aparelho não tem voz em português. A resposta aparece escrita logo abaixo.");
        }
      }
      if (!ativo.current) return;
      // Exame físico e despedida: a escuta para e a tela mostra o próximo passo.
      const etapa = atualizada.consulta_ia?.etapa;
      if (etapa === "exame_fisico" || etapa === "despedida") {
        escuta.current?.parar();
        escuta.current = null;
        setEstado("inicio");
        if (etapa === "exame_fisico") setHoraDoExame(true);
        else {
          setDespediu(true);
          setConfirmar(true);
        }
        return;
      }
      // Uma pausa curta, para o fim da voz do paciente não entrar no microfone.
      window.setTimeout(() => {
        if (!ativo.current) return;
        if (!escuta.current) {
          setEstado("inicio");
          return;
        }
        escuta.current.retomar();
        setEstado("ouvindo");
      }, 250);
    },
    [definir],
  );

  const voltarAOuvir = useCallback((mensagem: string | null) => {
    if (!ativo.current) return;
    setAviso(mensagem);
    escuta.current?.retomar();
    setEstado("ouvindo");
  }, []);

  const enviarFala = useCallback(
    async (wav: Blob) => {
      if (!id) return;
      setEstado("pensando");
      setErro(null);
      try {
        await responder(await api.perguntarFalando(id, wav, "pergunta.wav"));
      } catch (e) {
        if (e instanceof ErroApi && e.status === 422) voltarAOuvir("Não entendi. Pode repetir a pergunta?");
        else {
          setErro(textoDoErro(e));
          voltarAOuvir(null);
        }
      }
    },
    [id, responder, voltarAOuvir],
  );

  if (!id) return <Navigate to="/" replace />;
  if (sessao && sessao.status !== "conversando") return <Navigate to={rotaDaSessao(sessao)} replace />;

  const temAceite = (t: TipoTermo) =>
    Boolean(sessao?.consentimentos.some((c) => c.forma === "aceite" && c.versao_termo === t.versao));

  const ligar = async () => {
    setErro(null);
    setAviso(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setErro("Este navegador não grava áudio. Use a conversa por chat ou o Chrome atualizado.");
      return;
    }
    const nova = new Escuta({
      onComeco: () => ativo.current && setEstado("aluno"),
      onPergunta: (wav) => void enviarFala(wav),
      onNivel: (nivel) => esfera.current?.style.setProperty("--nivel", nivel.toFixed(3)),
    });
    try {
      await nova.iniciar();
    } catch (e) {
      nova.parar();
      setErro(mensagemMicrofone(e));
      return;
    }
    if (!ativo.current) {
      nova.parar();
      return;
    }
    escuta.current = nova;
    nova.mutar(mudo);
    setEstado("ouvindo");
  };

  /** O toque em começar: libera o som, confere o aceite do termo e liga o microfone. */
  const comecar = async () => {
    destravarSom();
    if (!termo || !sessao) {
      setErro("Não deu para carregar o termo de gravação. Tente de novo em instantes.");
      return;
    }
    if (!temAceite(termo)) {
      if (aceiteDono?.versao !== termo.versao) {
        setPedirAceite(true);
        return;
      }
      try {
        const c = await api.registrarConsentimento(id, {
          papel: "medico",
          nome_informado: perfil.nome.trim() || "Quem abriu a sessão",
          versao_termo: termo.versao,
          aceito: true,
        });
        definir((s) => s && { ...s, consentimentos: [...s.consentimentos, c] });
      } catch (e) {
        setErro(textoDoErro(e));
        return;
      }
    }
    await ligar();
  };

  const aceitou = (c: Consentimento) => {
    if (termo) aceitarComoDono(termo.versao);
    definir((s) => s && { ...s, consentimentos: [...s.consentimentos, c] });
    setPedirAceite(false);
    void ligar();
  };

  const alternarMudo = () => {
    const novo = !mudo;
    setMudo(novo);
    escuta.current?.mutar(novo);
  };

  const escrever = async () => {
    const pergunta = texto.trim();
    if (!pergunta || pergunta.length > LIMITE_PERGUNTA || (estado !== "ouvindo" && estado !== "inicio")) return;
    destravarSom();
    escuta.current?.pausar();
    setTexto("");
    setErro(null);
    setEstado("pensando");
    try {
      await responder(await api.perguntarAoPaciente(id, pergunta));
    } catch (e) {
      setErro(textoDoErro(e));
      setTexto(pergunta);
      if (escuta.current) voltarAOuvir(null);
      else setEstado("inicio");
    }
  };

  const encerrar = async () => {
    setEncerrando(true);
    escuta.current?.parar();
    escuta.current = null;
    pararVoz();
    try {
      const atualizada = await api.encerrarConversa(id);
      vibrar([10, 60, 10]);
      navegar(rotaDaSessao(atualizada), { replace: true });
    } catch (e) {
      setErro(textoDoErro(e));
      setEncerrando(false);
      setConfirmar(false);
      setEstado("inicio");
    }
  };

  const falas = sessao?.falas ?? [];
  const exames = sessao?.consulta_ia?.exame_fisico.length ?? 0;
  const perguntas = falas.filter((f) => f.papel === "entrevistador").length;
  const ultimaPergunta = [...falas].reverse().find((f) => f.papel === "entrevistador");
  const ultimaResposta =
    falas.length > 0 && falas[falas.length - 1]?.papel === "paciente" ? falas[falas.length - 1] : null;
  const ocupado = estado === "pensando" || estado === "paciente" || estado === "aluno";

  return (
    <Tela
      titulo="Consulta por voz"
      sobretitulo="Paciente pela IA"
      voltar="/"
      rotuloVoltar="Voltar ao início (a consulta fica salva)"
      className="app-tela-voz"
      canto={
        <button
          className="al-botao al-botao-texto"
          type="button"
          onClick={() => navegar(`/sessao/${id}/conversa`, { replace: true })}
          disabled={ocupado}
        >
          <IconeBalao />
          Chat
        </button>
      }
      rodape={
        <div className="app-voz-controles">
          <form
            className="app-voz-escrever"
            onSubmit={(e) => {
              e.preventDefault();
              void escrever();
            }}
          >
            <input
              type="text"
              placeholder="Escrever ao paciente"
              aria-label="Escrever ao paciente"
              value={texto}
              maxLength={LIMITE_PERGUNTA}
              onChange={(e) => setTexto(e.target.value)}
              disabled={!sessao || estado === "pensando" || estado === "paciente"}
            />
            {texto.trim() && (
              <button className="al-botao app-botao-icone" type="submit" aria-label="Enviar">
                <IconeEnviar />
              </button>
            )}
          </form>
          <button
            className={`al-botao app-voz-redondo${mudo ? " is-mudo" : ""}`}
            type="button"
            aria-label={mudo ? "Ligar o microfone" : "Silenciar o microfone"}
            aria-pressed={mudo}
            onClick={alternarMudo}
          >
            {mudo ? <IconeMicrofoneMudo /> : <IconeMicrofone />}
          </button>
          <button
            className="al-botao app-voz-redondo app-voz-encerrar"
            type="button"
            aria-label="Encerrar a consulta"
            onClick={() => {
              if (perguntas === 0) navegar("/", { replace: true, direcao: "voltar" });
              else setConfirmar(true);
            }}
            disabled={estado === "pensando"}
          >
            <IconeX />
          </button>
        </div>
      }
    >
      {erroSessao && <Aviso tipo="erro">{erroSessao}</Aviso>}
      {!sessao && !erroSessao && <Carregando texto="Chamando o paciente…" />}

      {sessao && (
        <div className="app-voz">
          <div
            ref={esfera}
            className={`app-esfera is-${estado}${mudo ? " is-mudo" : ""}`}
            role="img"
            aria-label={LEGENDA[estado]}
          >
            <Gotas />
          </div>
          <p className="app-voz-estado" aria-live="polite">
            {mudo && estado === "ouvindo" ? "Microfone silenciado." : LEGENDA[estado]}
          </p>
          {horaDoExame && estado === "inicio" && (
            <>
              <Guia>
                Hora do exame físico. Ele segue pelo chat: diga o que quer examinar, uma parte de cada vez, e eu conto o
                que você encontra.
              </Guia>
              <button
                className="al-botao al-botao-principal app-voz-comecar"
                type="button"
                onClick={() => navegar(`/sessao/${id}/conversa`, { replace: true })}
              >
                <IconeSelo />
                Ir para o exame físico
              </button>
            </>
          )}
          {estado === "inicio" && !horaDoExame && (
            <button
              className="al-botao al-botao-principal app-voz-comecar"
              type="button"
              onClick={() => void comecar()}
            >
              <IconeMicrofone />
              {perguntas > 0 ? "Continuar a conversa" : "Começar a conversa"}
            </button>
          )}
          {estado !== "inicio" && (ultimaPergunta || ultimaResposta) && (
            <div className="app-voz-legendas">
              {ultimaPergunta && <p className="app-voz-voce">Você: {ultimaPergunta.texto}</p>}
              {ultimaResposta && <p className="app-voz-paciente">Paciente: {ultimaResposta.texto}</p>}
            </div>
          )}
          {notaGuia && <Guia>{notaGuia}</Guia>}
          {aviso && <Aviso tipo="info">{aviso}</Aviso>}
          {erro && <Aviso tipo="erro">{erro}</Aviso>}
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
          titulo={despediu ? "O paciente se despediu" : "Encerrar a consulta?"}
          subtitulo={resumoDaConsulta(perguntas, exames)}
          onFechar={() => {
            setConfirmar(false);
            setDespediu(false);
          }}
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
              onClick={() => {
                setConfirmar(false);
                setDespediu(false);
              }}
            >
              {despediu ? "Chamar o paciente de volta" : "Continuar a consulta"}
            </button>
          </div>
        </Folha>
      )}
    </Tela>
  );
}
