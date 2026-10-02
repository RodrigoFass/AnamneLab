import { useState } from "react";
import { useAuth } from "../auth/Autenticacao";
import { supabase } from "../auth/supabase";
import { Aviso } from "../componentes/Aviso";
import { SeloDemonstracao } from "../componentes/AvisoDemonstracao";
import { IconeEnvelope, IconeVoltar } from "../componentes/Icones";
import { useTema } from "../util/tema";
import { useNavegar } from "../util/movimento";

const SENHA_MINIMA = 8;

type Modo = "entrar" | "criar" | "esqueci";

const TITULO: Record<Modo, string> = {
  entrar: "Entrar",
  criar: "Criar conta",
  esqueci: "Esqueci a senha",
};

/** Mensagem do Supabase Auth em português, sem repetir o texto técnico. */
function explicar(erro: unknown, modo: Modo): string {
  const m = (erro as { message?: string } | null)?.message?.toLowerCase() ?? "";
  if (m.includes("invalid login credentials")) return "E-mail ou senha não conferem.";
  if (m.includes("already registered") || m.includes("already been registered"))
    return "Já existe uma conta com este e-mail. Entre com a sua senha.";
  if (m.includes("email not confirmed")) return "Confirme o e-mail pelo link que mandamos antes de entrar.";
  if (m.includes("password")) return `A senha precisa de pelo menos ${SENHA_MINIMA} caracteres.`;
  if (m.includes("rate limit") || m.includes("security purposes"))
    return "Muitas tentativas seguidas. Espere um pouco e tente de novo.";
  if (m.includes("invalid") && m.includes("email")) return "Confira o e-mail digitado.";
  if (modo === "esqueci") return "Não deu para enviar o e-mail agora. Tente de novo em alguns instantes.";
  return "Não deu para continuar agora. Confira a internet e tente de novo.";
}

/**
 * Entrar ou criar conta com e-mail e senha. A conta nova entra direto, sem confirmar o
 * e-mail, e segue para o cadastro do perfil. No modo de demonstração a tela aparece em
 * /entrar só para ver o visual: nenhuma conta é criada.
 */
export function Login() {
  const tema = useTema();
  const navegar = useNavegar();
  const { loginAtivo } = useAuth();
  const [modo, setModo] = useState<Modo>("entrar");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [verSenha, setVerSenha] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [recado, setRecado] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const trocar = (m: Modo) => {
    setModo(m);
    setErro(null);
    setRecado(null);
  };

  const enviar = async () => {
    setEnviando(true);
    setErro(null);
    setRecado(null);
    try {
      if (!loginAtivo) {
        await new Promise((r) => window.setTimeout(r, 600));
        setRecado("Demonstração: o login fica ativo quando o app tiver o Supabase configurado.");
        return;
      }
      const sb = await supabase();
      const dados = { email: email.trim(), password: senha };
      if (modo === "entrar") {
        const { error } = await sb.auth.signInWithPassword(dados);
        if (error) throw error;
      } else if (modo === "criar") {
        const { data, error } = await sb.auth.signUp(dados);
        if (error) throw error;
        // Com "Confirm email" ligado no Supabase, a conta só entra depois do link.
        if (!data.session) setRecado("Conta criada. Abra o link que mandamos para o seu e-mail para entrar.");
      } else {
        const { error } = await sb.auth.resetPasswordForEmail(email.trim(), { redirectTo: window.location.origin });
        if (error) throw error;
        setRecado("Se houver uma conta com este e-mail, mandamos um link para criar uma senha nova.");
      }
    } catch (e) {
      setErro(explicar(e, modo));
    } finally {
      setEnviando(false);
    }
  };

  const pedeSenha = modo !== "esqueci";
  const senhaOk = !pedeSenha || senha.length >= (modo === "criar" ? SENHA_MINIMA : 1);

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

        <form
          className="app-grupo app-passo"
          key={modo}
          onSubmit={(e) => {
            e.preventDefault();
            void enviar();
          }}
        >
          <h1 className="app-titulo">{TITULO[modo]}</h1>
          {modo !== "esqueci" ? (
            <div className="app-alternar" role="group" aria-label="Entrar ou criar conta">
              {(["entrar", "criar"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  aria-pressed={modo === m}
                  onClick={() => trocar(m)}
                >
                  {m === "entrar" ? "Já tenho conta" : "Sou novo aqui"}
                </button>
              ))}
            </div>
          ) : (
            <p className="app-subtitulo-tela">Mandamos um link para o seu e-mail. Pelo link, você cria uma senha nova.</p>
          )}

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

          {pedeSenha && (
            <label className="app-campo">
              <span className="app-campo-rotulo">Senha</span>
              <span className="app-senha">
                <input
                  type={verSenha ? "text" : "password"}
                  autoComplete={modo === "criar" ? "new-password" : "current-password"}
                  minLength={modo === "criar" ? SENHA_MINIMA : undefined}
                  value={senha}
                  onChange={(e) => setSenha(e.target.value)}
                  required
                />
                <button
                  className="al-botao al-botao-texto"
                  type="button"
                  aria-pressed={verSenha}
                  onClick={() => setVerSenha((v) => !v)}
                >
                  {verSenha ? "Esconder" : "Mostrar"}
                </button>
              </span>
              {modo === "criar" && <span className="app-legenda">Pelo menos {SENHA_MINIMA} caracteres.</span>}
            </label>
          )}

          {erro && <Aviso tipo="erro">{erro}</Aviso>}
          {recado && (
            <p className="app-dica" role="status">
              <IconeEnvelope />
              {recado}
            </p>
          )}

          <button
            className={`al-botao al-botao-principal app-botao-largo${enviando ? " is-enviando" : ""}`}
            type="submit"
            disabled={!email.trim() || !senhaOk || enviando}
          >
            {enviando
              ? "Um instante…"
              : modo === "entrar"
                ? "Entrar"
                : modo === "criar"
                  ? "Criar conta"
                  : "Mandar o link"}
          </button>

          {modo === "entrar" && (
            <button className="al-botao al-botao-texto app-botao-largo" type="button" onClick={() => trocar("esqueci")}>
              Esqueci a senha
            </button>
          )}
          {modo === "esqueci" && (
            <button className="al-botao al-botao-texto app-botao-largo" type="button" onClick={() => trocar("entrar")}>
              Voltar para entrar
            </button>
          )}
          <p className="app-legenda app-centro">
            Ao entrar, você concorda em usar só casos simulados. Nunca grave pacientes reais.
          </p>
        </form>
      </main>
    </div>
  );
}

/** Depois do link de "esqueci a senha": a pessoa já entrou e escolhe a senha nova aqui. */
export function NovaSenha() {
  const { concluirRecuperacao } = useAuth();
  const [senha, setSenha] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const salvar = async () => {
    setEnviando(true);
    setErro(null);
    try {
      const sb = await supabase();
      const { error } = await sb.auth.updateUser({ password: senha });
      if (error) throw error;
      concluirRecuperacao();
    } catch (e) {
      setErro(explicar(e, "criar"));
      setEnviando(false);
    }
  };

  return (
    <div className="app-tela app-entrar">
      <main className="app-conteudo">
        <form
          className="app-grupo app-passo"
          onSubmit={(e) => {
            e.preventDefault();
            void salvar();
          }}
        >
          <h1 className="app-titulo">Crie uma senha nova</h1>
          <label className="app-campo">
            <span className="app-campo-rotulo">Senha nova</span>
            <input
              type="password"
              autoComplete="new-password"
              minLength={SENHA_MINIMA}
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              required
            />
            <span className="app-legenda">Pelo menos {SENHA_MINIMA} caracteres.</span>
          </label>
          {erro && <Aviso tipo="erro">{erro}</Aviso>}
          <button
            className="al-botao al-botao-principal app-botao-largo"
            type="submit"
            disabled={senha.length < SENHA_MINIMA || enviando}
          >
            {enviando ? "Salvando…" : "Salvar a senha"}
          </button>
        </form>
      </main>
    </div>
  );
}
