import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { loginAtivo, supabase } from "./supabase";

interface EstadoAuth {
  /** Login ativo neste ambiente (Supabase configurado). */
  loginAtivo: boolean;
  carregando: boolean;
  logado: boolean;
  email: string | null;
  sair: () => Promise<void>;
}

const ContextoAuth = createContext<EstadoAuth>({
  loginAtivo: false,
  carregando: false,
  logado: true,
  email: null,
  sair: async () => {},
});

export function ProvedorAuth({ children }: { children: ReactNode }) {
  const [carregando, setCarregando] = useState(loginAtivo);
  const [logado, setLogado] = useState(!loginAtivo);
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    if (!loginAtivo) return;
    let cancelado = false;
    let desinscrever: (() => void) | undefined;

    void supabase().then(async (sb) => {
      const { data } = await sb.auth.getSession();
      if (cancelado) return;
      setLogado(Boolean(data.session));
      setEmail(data.session?.user.email ?? null);
      setCarregando(false);
      const { data: inscricao } = sb.auth.onAuthStateChange((_evento, sessao) => {
        setLogado(Boolean(sessao));
        setEmail(sessao?.user.email ?? null);
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
  };

  return (
    <ContextoAuth.Provider value={{ loginAtivo, carregando, logado, email, sair }}>
      {children}
    </ContextoAuth.Provider>
  );
}

export function useAuth(): EstadoAuth {
  return useContext(ContextoAuth);
}
