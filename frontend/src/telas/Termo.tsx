import { useEffect, useRef, useState, type ReactNode } from "react";
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
import { aceitarComoDono, ehDono, useAceiteDono } from "../util/aceites";
import { lerNomes, ROTULO_ORIGEM } from "../util/nomes";
import { usePerfil } from "../util/perfil";
import { rotaDaSessao, useSessao } from "../util/sessao";
import { useNavegar } from "../util/movimento";

const ROTULO: Record<Papel, string> = { medico: "Faz o médico", paciente: "Faz o paciente" };
const OUTRO: Record<Papel, Papel> = { medico: "paciente", paciente: "medico" };

/** Ícone de cada parágrafo do termo, pelo assunto. O texto continua o do termo versionado. */
function iconeDoParagrafo(p: string): ReactNode {
  const t = p.toLowerCase();
  if (t.includes("apagad") || t.includes("exclus")) return <IconeLixeira />;
  if (t.includes("estados unidos")) return <IconeGlobo />;
  if (t.includes("simulado")) return <IconeAviso />;
  if (t.includes("gravad") || t.includes("para quê")) return <IconeMicrofone />;
  return <IconeSelo />;
}

interface PropsFolha {
  papel: Papel;
  nome: string;
  termo: TipoTermo;
  sessaoId: string;
  onRegistrado: (c: Consentimento) => void;
  onFechar: () => void;
}

/** Folha com o termo em tópicos e a marca de aceite de quem abriu a sessão. */
export function FolhaAceite({ papel, nome, termo, sessaoId, onRegistrado, onFechar }: PropsFolha) {
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
      onRegistrado(
        await api.registrarConsentimento(sessaoId, {
          papel,
          nome_informado: nome,
          versao_termo: termo.versao,
          aceito: true,
        }),
      );
    } catch (e) {
      setErro(textoDoErro(e));
      setEnviando(false);
    }
  };

  return (
    <Folha titulo="Termo de gravação" subtitulo="Você aceita uma vez, e ele vale para as próximas sessões." onFechar={onFechar}>
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
        <label className="app-marcar">
          <input type="checkbox" checked={aceito} onChange={(e) => setAceito(e.target.checked)} />
          <span>Li e aceito. Aviso o colega antes de cada gravação. Posso retirar o aceite no Perfil.</span>
        </label>
        {erro && <Aviso tipo="erro">{erro}</Aviso>}
        <button className="al-botao al-botao-principal app-botao-largo" type="submit" disabled={!aceito || enviando}>
          {enviando ? "Registrando…" : "Aceitar e gravar"}
        </button>
        <p className="app-legenda app-centro">Termo v{termo.versao}</p>
      </form>
    </Folha>
  );
}

export function Termo() {
  const { id } = useParams();
  const navegar = useNavegar();
  const { sessao, erro: erroSessao, definir } = useSessao(id);
  const perfil = usePerfil();
  const aceiteDono = useAceiteDono();
  const [termo, setTermo] = useState<TipoTermo | null>(null);
  const [erroTermo, setErroTermo] = useState<string | null>(null);
  const [nomes] = useState(lerNomes);
  const [aberta, setAberta] = useState(true);
  const [erroRegistro, setErroRegistro] = useState<string | null>(null);
  const registrando = useRef(false);

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

  // Quem usa o app é o dono: o papel com o nome do perfil, ou o médico se nenhum bate.
  const papelDono: Papel = ehDono(nomes.paciente, perfil.nome) && !ehDono(nomes.medico, perfil.nome) ? "paciente" : "medico";
  const papelColega = OUTRO[papelDono];
  const nomeDono = nomes[papelDono].trim() || perfil.nome.trim() || "Quem abriu a sessão";
  const nomeColega = nomes[papelColega].trim() || "Colega";

  const doPapel = (p: Papel) =>
    sessao?.consentimentos.find((c) => c.papel === p && (!termo || c.versao_termo === termo.versao));
  const donoValido = Boolean(termo && aceiteDono?.versao === termo.versao);
  const pronto = Boolean(doPapel("medico") && doPapel("paciente"));

  // Com o aceite do dono valendo, o app registra na sessão o aceite dele e o aviso ao colega,
  // e segue para a gravação. Se o registro falhar, a tela mostra o erro e o botão de tentar.
  useEffect(() => {
    if (!donoValido || !termo || !sessao || sessao.status !== "criada" || erroRegistro || registrando.current) return;
    if (pronto) {
      navegar(`/sessao/${sessao.id}/gravar`, { replace: true });
      return;
    }
    registrando.current = true;
    const registrar = async () => {
      const novos: Consentimento[] = [];
      if (!doPapel(papelDono)) {
        novos.push(
          await api.registrarConsentimento(sessao.id, {
            papel: papelDono,
            nome_informado: nomeDono,
            versao_termo: termo.versao,
            aceito: true,
          }),
        );
      }
      if (!doPapel(papelColega)) {
        novos.push(
          await api.registrarConsentimento(sessao.id, {
            papel: papelColega,
            nome_informado: nomeColega,
            versao_termo: termo.versao,
            aceito: true,
            forma: "declarado_pelo_dono",
          }),
        );
      }
      return novos;
    };
    registrar().then(
      (novos) => {
        registrando.current = false;
        definir((s) => s && { ...s, consentimentos: [...s.consentimentos, ...novos] });
      },
      (e: unknown) => {
        registrando.current = false;
        setErroRegistro(textoDoErro(e));
      },
    );
  }, [donoValido, termo, sessao, pronto, erroRegistro, papelDono, papelColega, nomeDono, nomeColega, definir, navegar]);

  if (!id) return <Navigate to="/" replace />;
  if (sessao && sessao.status !== "criada") return <Navigate to={rotaDaSessao(sessao)} replace />;

  const erro = erroSessao ?? erroTermo ?? erroRegistro;
  const carregando = (!termo || !sessao) && !erro;

  return (
    <Tela
      titulo="Antes de gravar"
      sobretitulo={sessao ? ROTULO_ORIGEM[sessao.origem_caso] : undefined}
      subtitulo={`Só você aceita o termo. Antes de gravar, avise ${nomeColega} que a conversa vai ser gravada.`}
      voltar="/"
      rotuloVoltar="Voltar ao início"
      rodape={
        !donoValido || erroRegistro ? (
          <button
            className="al-botao al-botao-principal app-botao-largo"
            type="button"
            onClick={() => (erroRegistro ? setErroRegistro(null) : setAberta(true))}
            disabled={!termo || !sessao}
          >
            {erroRegistro ? "Tentar de novo" : "Ler e aceitar o termo"}
          </button>
        ) : undefined
      }
    >
      <Aviso>Use só casos simulados. Não grave pacientes reais.</Aviso>
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      {carregando && <Carregando texto="Carregando o termo…" />}
      {termo && sessao && donoValido && !erro && <Carregando texto="Preparando a gravação…" />}

      {termo && sessao && (
        <ul className="app-lista">
          {([papelDono, papelColega] as Papel[]).map((papel) => {
            const feito = doPapel(papel);
            const nome = papel === papelDono ? nomeDono : nomeColega;
            return (
              <li key={papel} className="app-lista-linha">
                <Avatar nome={nome} papel={papel} />
                <span className="app-lista-texto">
                  <span className="app-lista-titulo">{nome}</span>
                  <span className="app-lista-meta">{ROTULO[papel]}</span>
                </span>
                {feito ? (
                  <span className="app-status app-status-ok">
                    <IconeCheck />
                    {papel === papelDono ? "Aceitou" : "Avisado"}
                  </span>
                ) : (
                  <span className="app-status">{papel === papelDono ? "Falta aceitar" : "Você avisa"}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {termo && sessao && aberta && !donoValido && (
        <FolhaAceite
          papel={papelDono}
          nome={nomeDono}
          termo={termo}
          sessaoId={sessao.id}
          onFechar={() => setAberta(false)}
          onRegistrado={(c) => {
            definir((s) => s && { ...s, consentimentos: [...s.consentimentos, c] });
            aceitarComoDono(termo.versao);
          }}
        />
      )}
    </Tela>
  );
}
