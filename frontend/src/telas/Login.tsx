import { useEffect, useState } from "react";
import { useAuth } from "../auth/Autenticacao";
import { supabase } from "../auth/supabase";
import { Aviso } from "../componentes/Aviso";
import { SeloDemonstracao } from "../componentes/AvisoDemonstracao";
import { Contador } from "../componentes/Contador";
import { IconeEnvelope, IconeVoltar } from "../componentes/Icones";
import { useTema } from "../util/tema";
import { useNavegar } from "../util/movimento";

const ESPERA_REENVIO_S = 30;

/**
 * Entrar com o e-mail: o app manda um link de acesso, sem senha. O primeiro link já
 * cria a conta, então entrar e se cadastrar são o mesmo passo. No modo de demonstração
 * a tela aparece em /entrar só para ver o visual: nenhum e-mail é enviado.
 */
export function Login() {
  const tema = useTema();
  const navegar = useNavegar();
  const { loginAtivo } = useAuth();
  const [email, setEmail] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [enviado, setEnviado] = useState(false);
  const [espera, setEspera] = useState(0);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (espera <= 0) return;
    const t = window.setTimeout(() => setEspera((s) => s - 1), 1000);
    return () => window.clearTimeout(t);
  }, [espera]);

  const entrar = async () => {
    setEnviando(true);
    setErro(null);
    try {
      if (loginAtivo) {
        const sb = await supabase();
        const { error } = await sb.auth.signInWithOtp({
          email: email.trim(),
          options: { emailRedirectTo: window.location.origin },
        });
        if (error) throw error;
      } else {
        await new Promise((r) => window.setTimeout(r, 700));
      }
      setEnviado(true);
      setEspera(ESPERA_REENVIO_S);
    } catch {
      setErro("Não deu para enviar o link. Confira o e-mail e tente de novo em alguns instantes.");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="app-tela app-entrar">
      <div className="app-topo-linha">
        {!loginAtivo ? (
          <button
            className="app-voltar"
            type="button"
            aria-label="Voltar ao perfil"
            onClick={() => navegar("/perfil", { direcao: "voltar" })}
          >
            <IconeVoltar />
          </button>
        ) : (
          <span />
        )}
        <SeloDemonstracao />
      </div>

      <main className="app-conteudo">
        <div className="app-marca-anima app-marca-pequena" aria-hidden="true">
          <img src={tema === "escuro" ? "/simbolo-escuro.svg" : "/simbolo-claro.svg"} width={56} height={56} alt="" />
        </div>

        {enviado ? (
          <section className="app-enviado app-passo" key="enviado" aria-live="polite">
            <span className="app-envelope" aria-hidden="true">
              <IconeEnvelope />
            </span>
            <h1 className="app-titulo">Confira o seu e-mail</h1>
            <p className="app-subtitulo-tela">
              Mandamos um link de acesso para <b>{email.trim()}</b>. Abra o link neste aparelho para entrar.
              {!loginAtivo && " (Demonstração: nenhum e-mail foi enviado.)"}
            </p>
            <button
              className="al-botao al-botao-secundario app-botao-largo"
              type="button"
              disabled={espera > 0 || enviando}
              onClick={() => void entrar()}
            >
              {espera > 0 ? (
                <>
                  Reenviar em <Contador texto={`0:${String(espera).padStart(2, "0")}`} rotulo={`${espera} segundos`} />
                </>
              ) : (
                "Reenviar o link"
              )}
            </button>
            <button className="al-botao al-botao-texto app-botao-largo" type="button" onClick={() => setEnviado(false)}>
              Usar outro e-mail
            </button>
          </section>
        ) : (
          <form
            className="app-grupo app-passo"
            key="form"
            onSubmit={(e) => {
              e.preventDefault();
              void entrar();
            }}
          >
            <h1 className="app-titulo">Entrar ou criar conta</h1>
            <p className="app-subtitulo-tela">
              Use o seu e-mail. Mandamos um link de acesso, sem senha. Na primeira vez, a conta é criada na hora.
            </p>
            <label className="app-campo">
              <span className="app-campo-rotulo">E-mail</span>
              <input
                type="email"
                autoComplete="email"
                inputMode="email"
                placeholder="voce@faculdade.edu.br"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            {erro && <Aviso tipo="erro">{erro}</Aviso>}
            <button
              className={`al-botao al-botao-principal app-botao-largo${enviando ? " is-enviando" : ""}`}
              type="submit"
              disabled={!email.trim() || enviando}
            >
              {enviando ? "Enviando o link…" : "Receber link de acesso"}
            </button>
            <p className="app-legenda app-centro">
              Ao entrar, você concorda em usar só casos simulados. Nunca grave pacientes reais.
            </p>
          </form>
        )}
      </main>
    </div>
  );
}
