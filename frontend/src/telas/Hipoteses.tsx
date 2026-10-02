import { useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import { api, textoDoErro } from "../api/cliente";
import { Aviso } from "../componentes/Aviso";
import { IconeArco, IconeCheck, IconeMais, IconeX } from "../componentes/Icones";
import { Carregando, Tela } from "../componentes/Tela";
import { movimentoReduzido, vibrar } from "../util/movimento";
import { rotaDaSessao, useSessao } from "../util/sessao";
import { useNavegar } from "../util/movimento";

const MAXIMO = 10;

export function Hipoteses() {
  const { id } = useParams();
  const navegar = useNavegar();
  const { sessao, erro: erroSessao } = useSessao(id, (s) => s.status === "corrigindo");
  const [hipoteses, setHipoteses] = useState<string[]>([]);
  const [rascunho, setRascunho] = useState("");
  /** Hipótese que está saindo (encolhe antes de sumir da lista). */
  const [saindo, setSaindo] = useState<number | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  if (!id) return <Navigate to="/" replace />;
  if (sessao && sessao.status !== "corrigindo" && sessao.status !== "aguardando_hipoteses") {
    return <Navigate to={rotaDaSessao(sessao)} replace />;
  }

  // O que está no campo também conta: ninguém perde a hipótese por não ter tocado em adicionar.
  const todas = [...hipoteses, rascunho.trim()].filter(Boolean).slice(0, MAXIMO);
  const pronta = sessao?.status === "aguardando_hipoteses";
  const cheia = hipoteses.length >= MAXIMO;

  const adicionar = () => {
    const h = rascunho.trim();
    if (!h || cheia) return;
    vibrar(8);
    setHipoteses((hs) => [...hs, h]);
    setRascunho("");
  };
  const tirar = (i: number) => {
    setHipoteses((hs) => hs.filter((_, j) => j !== i));
    setSaindo(null);
  };
  const remover = (i: number) => {
    if (movimentoReduzido()) tirar(i);
    else setSaindo(i);
  };

  const enviar = async () => {
    setEnviando(true);
    setErro(null);
    try {
      await api.enviarHipoteses(id, { hipoteses: todas });
      navegar(`/sessao/${id}/correcao`, { replace: true });
    } catch (e) {
      setErro(textoDoErro(e));
      setEnviando(false);
    }
  };

  return (
    <Tela
      titulo="Suas hipóteses"
      subtitulo="Antes de ver a correção, escreva o que você está pensando. Elas não valem nota."
      voltar="/"
      rotuloVoltar="Voltar ao início"
      rodape={
        <>
          <button
            className="al-botao al-botao-principal app-botao-largo"
            type="button"
            disabled={!pronta || todas.length === 0 || enviando}
            onClick={() => void enviar()}
          >
            {enviando
              ? "Enviando…"
              : !pronta
                ? "Esperando a correção terminar…"
                : todas.length === 0
                  ? "Escreva ao menos uma hipótese"
                  : "Ver correção"}
          </button>
          <p className="app-legenda app-centro">
            As hipóteses da IA aparecem depois, como sugestão para estudo.
          </p>
        </>
      }
    >
      {erroSessao && <Aviso tipo="erro">{erroSessao}</Aviso>}
      {!sessao && !erroSessao && <Carregando />}

      {sessao && (
        <>
          <form
            className="app-hipotese-campo"
            onSubmit={(e) => {
              e.preventDefault();
              adicionar();
            }}
          >
            <label className="app-campo app-campo-linha">
              <span className="app-so-leitor">Nova hipótese</span>
              <input
                type="text"
                maxLength={200}
                value={rascunho}
                disabled={cheia}
                placeholder={hipoteses.length === 0 ? "Por exemplo: síndrome coronariana aguda" : "Outra hipótese"}
                onChange={(e) => setRascunho(e.target.value)}
              />
            </label>
            <button
              className="al-botao al-botao-secundario app-botao-icone"
              type="submit"
              aria-label="Adicionar hipótese"
              disabled={!rascunho.trim() || cheia}
            >
              <IconeMais />
            </button>
          </form>
          {cheia && <p className="app-legenda">Você chegou ao limite de {MAXIMO} hipóteses.</p>}

          {hipoteses.length > 0 && (
            <ol className="app-chips-hipoteses">
              {hipoteses.map((h, i) => (
                <li
                  key={`${i}-${h}`}
                  className={`app-chip-hipotese${saindo === i ? " is-saindo" : ""}`}
                  onAnimationEnd={(e) => {
                    if (saindo === i && e.animationName === "app-chip-sai") tirar(i);
                  }}
                >
                  <span className="app-chip-numero" aria-hidden="true">
                    {i + 1}
                  </span>
                  <span className="app-chip-texto">{h}</span>
                  <button
                    className="app-chip-remover"
                    type="button"
                    aria-label={`Remover a hipótese ${h}`}
                    onClick={() => remover(i)}
                    disabled={saindo !== null}
                  >
                    <IconeX />
                  </button>
                </li>
              ))}
            </ol>
          )}

          {sessao.status === "corrigindo" ? (
            <p className="app-status" aria-live="polite">
              <IconeArco className="app-girando" />
              Corrigindo item por item enquanto você pensa…
            </p>
          ) : (
            <p className="app-status app-status-ok" aria-live="polite">
              <IconeCheck />
              Correção pronta. Ela aparece quando você enviar as hipóteses.
            </p>
          )}

          {erro && <Aviso tipo="erro">{erro}</Aviso>}
        </>
      )}
    </Tela>
  );
}
