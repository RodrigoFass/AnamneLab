import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { retirarAceiteDoDono } from "../util/aceites";
import { adotarPerfilDaConta, esquecerPerfilLocal } from "../util/perfil";
import { loginAtivo, supabase } from "./supabase";

interface EstadoAuth {
  /** Login ativo neste ambiente (Supabase configurado). */
  loginAtivo: boolean;
  carregando: boolean;
  logado: boolean;
  email: string | null;
  /** Entrou pelo link de "esqueci a senha": falta escolher a senha nova. */
  recuperandoSenha: boolean;
  concluirRecuperacao: () => void;
  sair: () => Promise<void>;
}

const ContextoAuth = createContext<EstadoAuth>({
  loginAtivo: false,
  carregando: false,
  logado: true,
  email: null,
  recuperandoSenha: false,
  concluirRecuperacao: () => {},
  sair: async () => {},
});

export function ProvedorAuth({ children }: { children: ReactNode }) {
  const [carregando, setCarregando] = useState(loginAtivo);
  const [logado, setLogado] = useState(!loginAtivo);
  const [email, setEmail] = useState<string | null>(null);
  const [recuperandoSenha, setRecuperandoSenha] = useState(false);

  useEffect(() => {
    if (!loginAtivo) return;
    let cancelado = false;
    let desinscrever: (() => void) | undefined;

    void supabase().then(async (sb) => {
      const { data } = await sb.auth.getSession();
      if (cancelado) return;
      setLogado(Boolean(data.session));
      setEmail(data.session?.user.email ?? null);
      adotarPerfilDaConta(data.session?.user.user_metadata ?? null);
      setCarregando(false);
      const { data: inscricao } = sb.auth.onAuthStateChange((evento, sessao) => {
        if (evento === "PASSWORD_RECOVERY") setRecuperandoSenha(true);
        setLogado(Boolean(sessao));
        setEmail(sessao?.user.email ?? null);
        adotarPerfilDaConta(sessao?.user.user_metadata ?? null);
      });
      desinscrever = () => inscricao.subscription.unsubscribe();
    });

    return () => {
      cancelado = true;
      desinscrever?.();
    };
  }, []);

  const sair = async () => {
    if (!loginAtivo) return;
    const sb = await supabase();
    await sb.auth.signOut();
    // O próximo a entrar neste aparelho começa do perfil da conta dele, e aceita o termo.
    esquecerPerfilLocal();
    retirarAceiteDoDono();
  };

  return (
    <ContextoAuth.Provider
      value={{
        loginAtivo,
        carregando,
        logado,
        email,
        recuperandoSenha,
        concluirRecuperacao: () => setRecuperandoSenha(false),
        sair,
      }}
    >
      {children}
    </ContextoAuth.Provider>
  );
}

export function useAuth(): EstadoAuth {
  return useContext(ContextoAuth);
}
