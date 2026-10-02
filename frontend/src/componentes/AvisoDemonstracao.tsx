import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "../api/cliente";

const ContextoDemonstracao = createContext(false);

/** Pergunta ao backend, uma vez, se o app roda com transcrição e correção de exemplo. */
export function ProvedorDemonstracao({ children }: { children: ReactNode }) {
  const [demonstracao, setDemonstracao] = useState(false);
  useEffect(() => {
    let ativo = true;
    api
      .saude()
      .then((r) => {
        if (ativo) setDemonstracao(r.modo_demonstracao === true);
      })
      .catch(() => {
        // Sem resposta, não há o que avisar: as telas mostram o erro de conexão.
      });
    return () => {
      ativo = false;
    };
  }, []);
  return <ContextoDemonstracao.Provider value={demonstracao}>{children}</ContextoDemonstracao.Provider>;
}

/** Selo discreto no topo de todas as telas, no modo de demonstração. */
export function SeloDemonstracao() {
  const demonstracao = useContext(ContextoDemonstracao);
  if (!demonstracao) return null;
  return (
    <span className="app-demo" title="Modo de demonstração: a transcrição e a correção são de exemplo.">
      Demonstração
      <span className="app-so-leitor">: a transcrição e a correção são de exemplo.</span>
    </span>
  );
}
