import { useState } from "react";
import { supabase } from "../auth/supabase";
import { Aviso } from "../componentes/Aviso";
import { Logotipo } from "../componentes/Logotipo";

/** Login por link mágico do Supabase. Só aparece quando o login está ativo. */
export function Login() {
  const [email, setEmail] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [enviado, setEnviado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const entrar = async () => {
    setEnviando(true);
    setErro(null);
    try {
      const sb = await supabase();
      const { error } = await sb.auth.signInWithOtp({
        email: email.trim(),
        options: { emailRedirectTo: window.location.origin },
      });
      if (error) throw error;
      setEnviado(true);
    } catch {
      setErro("Não deu para enviar o link. Confira o e-mail e tente de novo em alguns instantes.");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="app-tela app-inicio">
      <header className="app-inicio-topo">
        <Logotipo />
        <p className="app-assinatura">Pergunte melhor.</p>
        <p className="app-descritor">Treino de anamnese com correção na hora.</p>
      </header>
      <main className="app-conteudo">
        {enviado ? (
          <Aviso titulo="Confira o seu e-mail">
            Mandamos um link de acesso para {email.trim()}. Abra o link neste aparelho para entrar.
          </Aviso>
        ) : (
          <form
            className="app-grupo"
            onSubmit={(e) => {
              e.preventDefault();
              void entrar();
            }}
          >
            <h1 className="app-subtitulo">Entrar</h1>
            <p className="app-ajuda">Use o seu e-mail. Mandamos um link de acesso, sem senha.</p>
            <label className="app-campo">
              <span className="app-campo-rotulo">E-mail</span>
              <input
                type="email"
                autoComplete="email"
                inputMode="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            {erro && <Aviso tipo="erro">{erro}</Aviso>}
            <button
              className="al-botao al-botao-principal app-botao-largo"
              type="submit"
              disabled={!email.trim() || enviando}
            >
              {enviando ? "Enviando o link…" : "Receber link de acesso"}
            </button>
          </form>
        )}
      </main>
    </div>
  );
}
