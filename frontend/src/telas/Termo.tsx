import { useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { api, textoDoErro } from "../api/cliente";
import type { Consentimento, Papel, Termo as TipoTermo } from "../api/tipos";
import { Aviso } from "../componentes/Aviso";
import { IconeCheck } from "../componentes/Icones";
import { Carregando, Tela } from "../componentes/Tela";
import { rotaDaSessao, useSessao } from "../util/sessao";

const PAPEIS: { papel: Papel; titulo: string; ajuda: string }[] = [
  { papel: "medico", titulo: "Quem faz o médico", ajuda: "Você vai entrevistar e receber a correção." },
  { papel: "paciente", titulo: "Quem faz o paciente", ajuda: "Você responde como o paciente do caso." },
];

interface PropsAceite {
  papel: Papel;
  titulo: string;
  ajuda: string;
  termo: TipoTermo;
  sessaoId: string;
  registrado: Consentimento | undefined;
  onRegistrado: (c: Consentimento) => void;
}

function Aceite({ papel, titulo, ajuda, termo, sessaoId, registrado, onRegistrado }: PropsAceite) {
  const [nome, setNome] = useState("");
  const [aceito, setAceito] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  if (registrado) {
    return (
      <section className="app-aceite is-feito" aria-label={titulo}>
        <p className="app-aceite-titulo">{titulo}</p>
        <p className="app-status app-status-ok">
          <IconeCheck />
          Aceite registrado: {registrado.nome_informado}
        </p>
      </section>
    );
  }

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

  const idNome = `nome-${papel}`;
  return (
    <form
      className="app-aceite"
      aria-label={titulo}
      onSubmit={(e) => {
        e.preventDefault();
        void registrar();
      }}
    >
      <p className="app-aceite-titulo">{titulo}</p>
      <p className="app-ajuda">{ajuda}</p>
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
      <label className="app-marcar">
        <input type="checkbox" checked={aceito} onChange={(e) => setAceito(e.target.checked)} />
        <span>Li o termo e aceito que a minha voz seja gravada nessas condições.</span>
      </label>
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <button
        className="al-botao al-botao-secundario"
        type="submit"
        disabled={!aceito || !nome.trim() || enviando}
      >
        {enviando ? "Registrando…" : "Registrar meu aceite"}
      </button>
    </form>
  );
}

export function Termo() {
  const { id } = useParams();
  const navegar = useNavigate();
  const { sessao, erro: erroSessao, definir } = useSessao(id);
  const [termo, setTermo] = useState<TipoTermo | null>(null);
  const [erroTermo, setErroTermo] = useState<string | null>(null);

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

  return (
    <Tela
      titulo={termo?.titulo ?? "Termo de gravação"}
      voltar="/"
      rotuloVoltar="Voltar ao início"
      rodape={
        <button
          className="al-botao al-botao-principal app-botao-largo"
          type="button"
          disabled={!ambos}
          onClick={() => navegar(`/sessao/${id}/gravar`)}
        >
          {ambos ? "Ir para a gravação" : "Faltam os dois aceites"}
        </button>
      }
    >
      <Aviso>Use só casos simulados. Não grave pacientes reais.</Aviso>
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      {(!termo || !sessao) && !erro && <Carregando texto="Carregando o termo…" />}

      {termo && sessao && (
        <>
          <section className="app-termo" aria-label="Texto do termo">
            {termo.texto.split(/\n{2,}/).map((p, i) => (
              <p key={i}>{p}</p>
            ))}
            <p className="app-legenda">Versão {termo.versao} do termo.</p>
          </section>

          <p className="app-ajuda">
            Cada um lê e aceita no mesmo celular. A gravação só fica liberada depois dos dois
            aceites.
          </p>

          {PAPEIS.map((p) => (
            <Aceite
              key={p.papel}
              {...p}
              termo={termo}
              sessaoId={sessao.id}
              registrado={doPapel(p.papel)}
              onRegistrado={(c) =>
                definir((s) => s && { ...s, consentimentos: [...s.consentimentos, c] })
              }
            />
          ))}
        </>
      )}
    </Tela>
  );
}
