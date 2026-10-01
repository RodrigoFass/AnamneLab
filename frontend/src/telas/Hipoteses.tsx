import { useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { api, textoDoErro } from "../api/cliente";
import { Aviso } from "../componentes/Aviso";
import { BarraProgresso } from "../componentes/BarraProgresso";
import { IconeArco, IconeCheck, IconeMais } from "../componentes/Icones";
import { Carregando, Tela } from "../componentes/Tela";
import { rotaDaSessao, useSessao } from "../util/sessao";

const MAXIMO = 10;

export function Hipoteses() {
  const { id } = useParams();
  const navegar = useNavigate();
  const { sessao, erro: erroSessao } = useSessao(id, (s) => s.status === "corrigindo");
  const [hipoteses, setHipoteses] = useState<string[]>([""]);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  if (!id) return <Navigate to="/" replace />;
  if (sessao && sessao.status !== "corrigindo" && sessao.status !== "aguardando_hipoteses") {
    return <Navigate to={rotaDaSessao(sessao)} replace />;
  }

  const preenchidas = hipoteses.map((h) => h.trim()).filter(Boolean);
  const pronta = sessao?.status === "aguardando_hipoteses";

  const mudar = (i: number, valor: string) =>
    setHipoteses((hs) => hs.map((h, j) => (j === i ? valor : h)));
  const remover = (i: number) =>
    setHipoteses((hs) => (hs.length === 1 ? [""] : hs.filter((_, j) => j !== i)));
  const adicionar = () => setHipoteses((hs) => (hs.length < MAXIMO ? [...hs, ""] : hs));

  const enviar = async () => {
    setEnviando(true);
    setErro(null);
    try {
      await api.enviarHipoteses(id, { hipoteses: preenchidas });
      navegar(`/sessao/${id}/correcao`, { replace: true });
    } catch (e) {
      setErro(textoDoErro(e));
      setEnviando(false);
    }
  };

  return (
    <Tela
      titulo="Suas hipóteses"
      voltar="/"
      rotuloVoltar="Voltar ao início"
      rodape={
        <button
          className="al-botao al-botao-principal app-botao-largo"
          type="button"
          disabled={!pronta || preenchidas.length === 0 || enviando}
          onClick={() => void enviar()}
        >
          {enviando
            ? "Enviando…"
            : !pronta
              ? "Esperando a correção terminar…"
              : preenchidas.length === 0
                ? "Escreva ao menos uma hipótese"
                : "Ver a correção"}
        </button>
      }
    >
      {erroSessao && <Aviso tipo="erro">{erroSessao}</Aviso>}
      {!sessao && !erroSessao && <Carregando />}

      {sessao && (
        <>
          <p>
            Antes de ver a correção, escreva as hipóteses que você levantou com essa conversa. Elas
            não valem nota: servem para você comparar o seu raciocínio depois.
          </p>

          {sessao.status === "corrigindo" ? (
            <section className="app-processando">
              <p className="app-status" aria-live="polite">
                <IconeArco className="app-girando" />
                Montando a anamnese e corrigindo item por item…
              </p>
              <BarraProgresso valor={sessao.progresso} rotulo="Progresso da correção" />
            </section>
          ) : (
            <p className="app-status app-status-ok" aria-live="polite">
              <IconeCheck />
              Correção pronta. Ela aparece quando você enviar as hipóteses.
            </p>
          )}

          <fieldset className="app-grupo">
            <legend className="app-subtitulo">Hipóteses</legend>
            <ol className="app-lista-hipoteses">
              {hipoteses.map((h, i) => (
                <li key={i}>
                  <label className="app-campo app-campo-linha">
                    <span className="app-so-leitor">Hipótese {i + 1}</span>
                    <input
                      type="text"
                      maxLength={200}
                      value={h}
                      placeholder={i === 0 ? "Por exemplo: síndrome coronariana aguda" : ""}
                      onChange={(e) => mudar(i, e.target.value)}
                    />
                  </label>
                  <button
                    className="al-botao al-botao-texto"
                    type="button"
                    aria-label={`Remover a hipótese ${i + 1}`}
                    onClick={() => remover(i)}
                  >
                    Remover
                  </button>
                </li>
              ))}
            </ol>
            {hipoteses.length < MAXIMO ? (
              <button className="al-botao al-botao-texto" type="button" onClick={adicionar}>
                <IconeMais />
                Adicionar hipótese
              </button>
            ) : (
              <p className="app-legenda">Você chegou ao limite de {MAXIMO} hipóteses.</p>
            )}
          </fieldset>

          {erro && <Aviso tipo="erro">{erro}</Aviso>}
        </>
      )}
    </Tela>
  );
}
