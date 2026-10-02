import { useEffect, useRef, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import { api, textoDoErro } from "../api/cliente";
import { Aviso } from "../componentes/Aviso";
import { Avatar } from "../componentes/Avatar";
import { Folha } from "../componentes/Folha";
import { IconeAviso, IconeBalao, IconeEnviar, IconeLampada, IconeSelo } from "../componentes/Icones";
import { Carregando, Tela } from "../componentes/Tela";
import { rotaDaSessao, useQueixas, useSessao } from "../util/sessao";
import { useNavegar, vibrar } from "../util/movimento";

/** Igual a MAXIMO_PERGUNTA no backend. */
const LIMITE_PERGUNTA = 1000;

const PONTOS = [
  { icone: <IconeBalao />, texto: "Você faz o médico e escreve as perguntas. A IA responde como o paciente." },
  { icone: <IconeLampada />, texto: "Ela só conta o que você perguntar, do jeito de quem não é da saúde." },
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

/** A consulta por escrito: perguntas à direita, respostas do paciente à esquerda. */
export function Conversa() {
  const { id } = useParams();
  const navegar = useNavegar();
  const { sessao, erro: erroSessao, definir } = useSessao(id);
  const [texto, setTexto] = useState("");
  const [esperando, setEsperando] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [confirmar, setConfirmar] = useState(false);
  const [encerrando, setEncerrando] = useState(false);
  const fim = useRef<HTMLDivElement>(null);
  const campo = useRef<HTMLTextAreaElement>(null);

  const falas = sessao?.falas ?? [];
  const perguntas = falas.filter((f) => f.papel === "entrevistador").length;
  const tamanho = texto.trim().length;
  const passou = tamanho > LIMITE_PERGUNTA;

  useEffect(() => {
    fim.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [falas.length, esperando]);

  if (!id) return <Navigate to="/" replace />;
  if (sessao && sessao.status !== "conversando") return <Navigate to={rotaDaSessao(sessao)} replace />;

  const enviar = async () => {
    const pergunta = texto.trim();
    if (!pergunta || esperando || pergunta.length > LIMITE_PERGUNTA) return;
    setEsperando(pergunta);
    setTexto("");
    setErro(null);
    try {
      const atualizada = await api.perguntarAoPaciente(id, pergunta);
      definir(() => atualizada);
      vibrar(6);
    } catch (e) {
      setErro(textoDoErro(e));
      setTexto(pergunta); // a pergunta volta para o campo, para tentar de novo
    } finally {
      setEsperando(null);
      campo.current?.focus();
    }
  };

  const encerrar = async () => {
    setEncerrando(true);
    setErro(null);
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
          disabled={!sessao || perguntas === 0 || Boolean(esperando)}
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
          {tamanho > LIMITE_PERGUNTA * 0.8 && (
            <p id="tamanho-pergunta" className={`app-perguntar-conta${passou ? " is-passou" : ""}`} aria-live="polite">
              {passou
                ? `Pergunta longa demais: ${tamanho} de ${LIMITE_PERGUNTA} caracteres. Divida em duas.`
                : `${tamanho} de ${LIMITE_PERGUNTA} caracteres`}
            </p>
          )}
          <textarea
            ref={campo}
            rows={1}
            placeholder="Escreva a sua pergunta"
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
          <button
            className="al-botao al-botao-principal app-botao-icone"
            type="submit"
            aria-label="Enviar pergunta"
            disabled={!tamanho || passou || Boolean(esperando) || !sessao}
          >
            <IconeEnviar />
          </button>
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
          {falas.map((f, i) =>
            f.papel === "entrevistador" ? (
              <p key={i} className="app-bolha app-bolha-medico">
                {f.texto}
              </p>
            ) : (
              <div key={i} className="app-bolha-linha">
                <Avatar nome="Paciente" papel="paciente" tamanho={28} avatar="" />
                <p className="app-bolha app-bolha-paciente">{f.texto}</p>
              </div>
            ),
          )}
          {esperando && (
            <>
              <p className="app-bolha app-bolha-medico is-enviando">{esperando}</p>
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
          {erro && <Aviso tipo="erro">{erro}</Aviso>}
          <div ref={fim} />
        </div>
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
