import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Tema = "claro" | "escuro";

const consulta = "(prefers-color-scheme: dark)";

function temaDoSistema(): Tema {
  return window.matchMedia?.(consulta).matches ? "escuro" : "claro";
}

const ContextoTema = createContext<Tema>("claro");

/**
 * Segue o tema do sistema ao vivo. O tokens.css só troca de tema pelo atributo
 * data-theme="escuro" no <html>, então o atributo acompanha o prefers-color-scheme.
 */
export function ProvedorTema({ children }: { children: ReactNode }) {
  const [tema, setTema] = useState<Tema>(temaDoSistema);

  useEffect(() => {
    const mq = window.matchMedia(consulta);
    const aoMudar = () => setTema(mq.matches ? "escuro" : "claro");
    mq.addEventListener("change", aoMudar);
    return () => mq.removeEventListener("change", aoMudar);
  }, []);

  useEffect(() => {
    const raiz = document.documentElement;
    if (tema === "escuro") raiz.setAttribute("data-theme", "escuro");
    else raiz.removeAttribute("data-theme");
  }, [tema]);

  return <ContextoTema.Provider value={tema}>{children}</ContextoTema.Provider>;
}

export function useTema(): Tema {
  return useContext(ContextoTema);
}
