import { useEffect, useState, type ReactNode } from "react";
import { Navigate, useParams } from "react-router-dom";
import { api, textoDoErro } from "../api/cliente";
import type { Consentimento, Papel, Termo as TipoTermo } from "../api/tipos";
import { Aviso } from "../componentes/Aviso";
import { Avatar } from "../componentes/Avatar";
import { Folha } from "../componentes/Folha";
import {
  IconeAviso,
  IconeCheck,
  IconeGlobo,
  IconeLixeira,
  IconeMicrofone,
  IconeSelo,
} from "../componentes/Icones";
import { Carregando, Tela } from "../componentes/Tela";
import { lerNomes, ROTULO_ORIGEM } from "../util/nomes";
import { rotaDaSessao, useSessao } from "../util/sessao";
import { useNavegar } from "../util/movimento";

const PAPEIS: { papel: Papel; rotulo: string; frase: string }[] = [
  { papel: "medico", rotulo: "Faz o médico", frase: "Você vai fazer o médico nesta sessão." },
  { papel: "paciente", rotulo: "Faz o paciente", frase: "Você vai fazer o paciente nesta sessão." },
];

/** Ícone de cada parágrafo do termo, pelo assunto. O texto continua o do termo versionado. */
function iconeDoParagrafo(p: string): ReactNode {
  const t = p.toLowerCase();
  if (t.includes("apagad") || t.includes("exclus")) return <IconeLixeira />;
  if (t.includes("estados unidos")) return <IconeGlobo />;
  if (t.includes("simulado")) return <IconeAviso />;
  if (t.includes("gravad") || t.includes("para quê")) return <IconeMicrofone />;
  return <IconeSelo />;
}

interface PropsAceite {
  papel: Papel;
  frase: string;
  nomeInicial: string;
  termo: TipoTermo;
  sessaoId: string;
  ultimo: boolean;
  onRegistrado: (c: Consentimento) => void;
  onFechar: () => void;
}

/** Folha de aceite de uma pessoa: o termo inteiro em tópicos, nome e a marca de aceite. */
function FolhaAceite({ papel, frase, nomeInicial, termo, sessaoId, ultimo, onRegistrado, onFechar }: PropsAceite) {
  const [nome, setNome] = useState(nomeInicial);
  const [aceito, setAceito] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const paragrafos = termo.texto.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
  // O primeiro ("leia com atenção") e o último ("ao aceitar…") emolduram os tópicos.
  const topicos = paragrafos.length > 2 ? paragrafos.slice(1, -1) : paragrafos;
  const fecho = paragrafos.length > 2 ? paragrafos[paragrafos.length - 1] : null;

  const registrar = async () => {
    setEnviando(true);
    setErro(null);
    try {
      const c = await api.registrarConsentimento(sessaoId, {
        papel,
        nome_informado: nome.trim(),
        versao_termo: termo.versao,
        aceito: true,
      });
      onRegistrado(c);
    } catch (e) {
      setErro(textoDoErro(e));
      setEnviando(false);
    }
  };

  const titulo = nome.trim() ? `${nome.trim()}, antes de gravar` : "Antes de gravar";
  const idNome = `nome-${papel}`;

  return (
    <Folha titulo={titulo} subtitulo={frase} onFechar={onFechar}>
      <form
        className="app-grupo"
        onSubmit={(e) => {
          e.preventDefault();
          void registrar();
        }}
      >
        <ul className="app-topicos">
          {topicos.map((p) => (
            <li key={p}>
              {iconeDoParagrafo(p)}
              <span>{p}</span>
            </li>
          ))}
        </ul>
        {fecho && <p className="app-legenda">{fecho}</p>}

        {!nomeInicial && (
          <label className="app-campo" htmlFor={idNome}>
            <span className="app-campo-rotulo">Seu nome</span>
            <input
              id={idNome}
              type="text"
              autoComplete="off"
              maxLength={120}
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              required
            />
          </label>
        )}

        <label className="app-marcar">
          <input type="checkbox" checked={aceito} onChange={(e) => setAceito(e.target.checked)} />
          <span>Li e aceito a gravação desta sessão.</span>
        </label>
        {erro && <Aviso tipo="erro">{erro}</Aviso>}
        <button
          className="al-botao al-botao-principal app-botao-largo"
          type="submit"
          disabled={!aceito || !nome.trim() || enviando}
        >
          {enviando ? "Registrando…" : ultimo ? "Aceitar e gravar" : "Aceitar"}
        </button>
        <p className="app-legenda app-centro">Termo v{termo.versao} · não precisa criar conta</p>
      </form>
    </Folha>
  );
}

export function Termo() {
  const { id } = useParams();
  const navegar = useNavegar();
  const { sessao, erro: erroSessao, definir } = useSessao(id);
  const [termo, setTermo] = useState<TipoTermo | null>(null);
  const [erroTermo, setErroTermo] = useState<string | null>(null);
  const [nomes] = useState(lerNomes);
  const [aberta, setAberta] = useState(true);

  useEffect(() => {
    let ativo = true;
    api.termo().then(
      (t) => ativo && setTermo(t),
      (e: unknown) => ativo && setErroTermo(textoDoErro(e)),
    );
    return () => {
      ativo = false;
    };
  }, []);

  if (!id) return <Navigate to="/" replace />;
  if (sessao && sessao.status !== "criada") return <Navigate to={rotaDaSessao(sessao)} replace />;

  const erro = erroSessao ?? erroTermo;
  const doPapel = (p: Papel) =>
    sessao?.consentimentos.find((c) => c.papel === p && (!termo || c.versao_termo === termo.versao));
  const ambos = Boolean(doPapel("medico") && doPapel("paciente"));
  const vez = PAPEIS.find((p) => !doPapel(p.papel));
  const nomeDe = (p: Papel) => doPapel(p)?.nome_informado ?? nomes[p];

  return (
    <Tela
      titulo="Antes de gravar"
      sobretitulo={sessao ? ROTULO_ORIGEM[sessao.origem_caso] : undefined}
      subtitulo="Cada um lê e aceita no mesmo celular. A gravação só começa depois dos dois aceites."
      voltar="/"
      rotuloVoltar="Voltar ao início"
      rodape={
        <button
          className="al-botao al-botao-principal app-botao-largo"
          type="button"
          onClick={() => (ambos ? navegar(`/sessao/${id}/gravar`) : setAberta(true))}
          disabled={!termo || !sessao}
        >
          {ambos ? "Ir para a gravação" : `Ler e aceitar${vez && nomeDe(vez.papel) ? `: ${nomeDe(vez.papel)}` : ""}`}
        </button>
      }
    >
      <Aviso>Use só casos simulados. Não grave pacientes reais.</Aviso>
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      {(!termo || !sessao) && !erro && <Carregando texto="Carregando o termo…" />}

      {termo && sessao && (
        <ul className="app-lista">
          {PAPEIS.map(({ papel, rotulo }) => {
            const feito = doPapel(papel);
            return (
              <li key={papel} className="app-lista-linha">
                <Avatar nome={nomeDe(papel)} papel={papel} />
                <span className="app-lista-texto">
                  <span className="app-lista-titulo">{nomeDe(papel) || rotulo}</span>
                  <span className="app-lista-meta">{rotulo}</span>
                </span>
                {feito ? (
                  <span className="app-status app-status-ok">
                    <IconeCheck />
                    Aceitou
                  </span>
                ) : (
                  <span className="app-status">Falta aceitar</span>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {termo && sessao && aberta && vez && (
        <FolhaAceite
          key={vez.papel}
          papel={vez.papel}
          frase={vez.frase}
          nomeInicial={nomes[vez.papel]}
          termo={termo}
          sessaoId={sessao.id}
          ultimo={PAPEIS.filter((p) => !doPapel(p.papel)).length === 1}
          onFechar={() => setAberta(false)}
          onRegistrado={(c) => {
            definir((s) => s && { ...s, consentimentos: [...s.consentimentos, c] });
            if (PAPEIS.filter((p) => !doPapel(p.papel)).length === 1) {
              navegar(`/sessao/${id}/gravar`);
            }
          }}
        />
      )}
    </Tela>
  );
}
