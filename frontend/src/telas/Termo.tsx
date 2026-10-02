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
import {
  aceitarComoDono,
  colegaJaLeu,
  ehDono,
  lembrarColega,
  useAceiteDono,
} from "../util/aceites";
import { lerNomes, ROTULO_ORIGEM } from "../util/nomes";
import { usePerfil } from "../util/perfil";
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

/**
 * Como a folha aparece:
 * - "dono": o dono do perfil aceita uma vez, e o aceite vale para as próximas sessões;
 * - "completo": colega que ainda não leu esta versão do termo neste aparelho;
 * - "curto": colega que já leu; confirma a gravação desta sessão com um resumo.
 */
type ModoAceite = "dono" | "completo" | "curto";

const RESUMO = [
  { icone: <IconeMicrofone />, texto: "A voz de vocês dois é gravada e vira texto para corrigir a anamnese." },
  { icone: <IconeLixeira />, texto: "O áudio é apagado logo depois da transcrição." },
  { icone: <IconeAviso />, texto: "O caso é simulado: nada de dados de paciente real." },
];

const MARCA: Record<Exclude<ModoAceite, "curto">, string> = {
  dono: "Li e aceito. Vale para as minhas próximas sessões neste aparelho; posso retirar no Perfil.",
  completo: "Li e aceito a gravação desta sessão.",
};

interface PropsAceite {
  papel: Papel;
  frase: string;
  nomeInicial: string;
  modo: ModoAceite;
  termo: TipoTermo;
  sessaoId: string;
  ultimo: boolean;
  onRegistrado: (c: Consentimento) => void;
  onFechar: () => void;
}

/** Folha de aceite de uma pessoa: o termo em tópicos (ou o resumo), nome e a marca de aceite. */
function FolhaAceite({ papel, frase, nomeInicial, modo, termo, sessaoId, ultimo, onRegistrado, onFechar }: PropsAceite) {
  const [nome, setNome] = useState(nomeInicial);
  const [aceito, setAceito] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [verCompleto, setVerCompleto] = useState(modo !== "curto");
  // Na versão curta, o próprio botão "Concordo" é o aceite: um toque só.
  const marcado = modo === "curto" || aceito;

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
        {verCompleto ? (
          <>
            <ul className="app-topicos">
              {topicos.map((p) => (
                <li key={p}>
                  {iconeDoParagrafo(p)}
                  <span>{p}</span>
                </li>
              ))}
            </ul>
            {fecho && <p className="app-legenda">{fecho}</p>}
          </>
        ) : (
          <>
            <p className="app-ajuda">Você já leu este termo neste aparelho. Em resumo:</p>
            <ul className="app-topicos">
              {RESUMO.map((r) => (
                <li key={r.texto}>
                  {r.icone}
                  <span>{r.texto}</span>
                </li>
              ))}
            </ul>
            <button className="al-botao al-botao-texto app-link" type="button" onClick={() => setVerCompleto(true)}>
              Ler o termo completo
            </button>
          </>
        )}

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

        {modo === "curto" ? (
          <p className="app-legenda">Ao tocar em Concordo, você aceita a gravação desta sessão.</p>
        ) : (
          <label className="app-marcar">
            <input type="checkbox" checked={aceito} onChange={(e) => setAceito(e.target.checked)} />
            <span>{MARCA[modo]}</span>
          </label>
        )}
        {erro && <Aviso tipo="erro">{erro}</Aviso>}
        <button
          className="al-botao al-botao-principal app-botao-largo"
          type="submit"
          disabled={!marcado || !nome.trim() || enviando}
        >
          {enviando
            ? "Registrando…"
            : modo === "curto"
              ? ultimo
                ? "Concordo e gravar"
                : "Concordo"
              : ultimo
                ? "Aceitar e gravar"
                : "Aceitar"}
        </button>
        <p className="app-legenda app-centro">
          Termo v{termo.versao}
          {modo === "dono" ? "" : " · não precisa criar conta"}
        </p>
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
  const [aceitouAgora, setAceitouAgora] = useState(false);
  const [erroDono, setErroDono] = useState<string | null>(null);
  const registrandoDono = useRef<string | null>(null);

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

  const doPapel = (p: Papel) =>
    sessao?.consentimentos.find((c) => c.papel === p && (!termo || c.versao_termo === termo.versao));
  const nomeDe = (p: Papel) => doPapel(p)?.nome_informado ?? nomes[p];
  const ambos = Boolean(doPapel("medico") && doPapel("paciente"));

  // O dono do perfil que já aceitou esta versão do termo não vê a folha: o app registra o
  // aceite dele nesta sessão sozinho. Se o registro falhar, a folha volta a aparecer.
  const papelDono = PAPEIS.find((p) => ehDono(nomeDe(p.papel), perfil.nome))?.papel ?? null;
  const nomeDono = papelDono ? nomeDe(papelDono).trim() : "";
  const automatico = Boolean(termo && papelDono && aceiteDono?.versao === termo.versao && !erroDono);
  const donoFeito = papelDono ? Boolean(doPapel(papelDono)) : false;

  useEffect(() => {
    if (!automatico || !termo || !sessao || !papelDono || donoFeito || sessao.status !== "criada") return;
    const chave = `${sessao.id}:${papelDono}`;
    if (registrandoDono.current === chave) return;
    registrandoDono.current = chave;
    api
      .registrarConsentimento(sessao.id, {
        papel: papelDono,
        nome_informado: nomeDono,
        versao_termo: termo.versao,
        aceito: true,
      })
      .then(
        (c) => definir((s) => s && { ...s, consentimentos: [...s.consentimentos, c] }),
        (e: unknown) => setErroDono(textoDoErro(e)),
      );
  }, [automatico, termo, sessao, papelDono, nomeDono, donoFeito, definir]);

  // Depois de um aceite feito agora, com os dois registrados, segue para a gravação.
  useEffect(() => {
    if (aceitouAgora && ambos && id) navegar(`/sessao/${id}/gravar`);
  }, [aceitouAgora, ambos, id, navegar]);

  if (!id) return <Navigate to="/" replace />;
  if (sessao && sessao.status !== "criada") return <Navigate to={rotaDaSessao(sessao)} replace />;

  const erro = erroSessao ?? erroTermo ?? erroDono;
  const pendentes = PAPEIS.filter((p) => !doPapel(p.papel) && !(automatico && p.papel === papelDono));
  const vez = pendentes[0];
  const modoDe = (p: Papel): ModoAceite =>
    ehDono(nomeDe(p), perfil.nome) ? "dono" : termo && colegaJaLeu(nomeDe(p), termo.versao) ? "curto" : "completo";

  return (
    <Tela
      titulo="Antes de gravar"
      sobretitulo={sessao ? ROTULO_ORIGEM[sessao.origem_caso] : undefined}
      subtitulo={
        automatico && !ambos
          ? "O seu aceite do termo já vale. Falta só o do colega, que confirma neste celular."
          : "Cada um lê e aceita no mesmo celular. A gravação só começa depois dos dois aceites."
      }
      voltar="/"
      rotuloVoltar="Voltar ao início"
      rodape={
        <button
          className="al-botao al-botao-principal app-botao-largo"
          type="button"
          onClick={() => (ambos ? navegar(`/sessao/${id}/gravar`) : setAberta(true))}
          disabled={!termo || !sessao || (!ambos && !vez)}
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
                ) : automatico && papel === papelDono ? (
                  <span className="app-status">Registrando…</span>
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
          modo={modoDe(vez.papel)}
          termo={termo}
          sessaoId={sessao.id}
          ultimo={pendentes.length === 1}
          onFechar={() => setAberta(false)}
          onRegistrado={(c) => {
            if (modoDe(vez.papel) === "dono") aceitarComoDono(termo.versao);
            else lembrarColega(c.nome_informado, termo.versao);
            definir((s) => s && { ...s, consentimentos: [...s.consentimentos, c] });
            setAceitouAgora(true);
          }}
        />
      )}
    </Tela>
  );
}
