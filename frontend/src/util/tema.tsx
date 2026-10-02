import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { usePreferencias } from "./preferencias";

export type Tema = "claro" | "escuro";

const consulta = "(prefers-color-scheme: dark)";

function temaDoSistema(): Tema {
  return window.matchMedia?.(consulta).matches ? "escuro" : "claro";
}

const ContextoTema = createContext<Tema>("claro");

/**
 * Tema e outras configurações no <html>. O tokens.css só troca de tema pelo atributo
 * data-theme="escuro", então o atributo segue a escolha do aluno ou, no automático, o
 * prefers-color-scheme ao vivo. data-texto e data-movimento vêm das configurações.
 */
export function ProvedorTema({ children }: { children: ReactNode }) {
  const preferencias = usePreferencias();
  const [sistema, setSistema] = useState<Tema>(temaDoSistema);
  const tema: Tema = preferencias.tema === "automatico" ? sistema : preferencias.tema;

  useEffect(() => {
    const mq = window.matchMedia(consulta);
    const aoMudar = () => setSistema(mq.matches ? "escuro" : "claro");
    mq.addEventListener("change", aoMudar);
    return () => mq.removeEventListener("change", aoMudar);
  }, []);

  useEffect(() => {
    const raiz = document.documentElement;
    if (tema === "escuro") raiz.setAttribute("data-theme", "escuro");
    else raiz.removeAttribute("data-theme");
  }, [tema]);

  useEffect(() => {
    const raiz = document.documentElement;
    if (preferencias.texto === "normal") delete raiz.dataset.texto;
    else raiz.dataset.texto = preferencias.texto;
    if (preferencias.movimento === "reduzido") raiz.dataset.movimento = "reduzido";
    else delete raiz.dataset.movimento;
  }, [preferencias.texto, preferencias.movimento]);

  return <ContextoTema.Provider value={tema}>{children}</ContextoTema.Provider>;
}

export function useTema(): Tema {
  return useContext(ContextoTema);
}
