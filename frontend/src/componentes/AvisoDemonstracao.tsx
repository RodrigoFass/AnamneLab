import { useEffect, useState } from "react";
import { api } from "../api/cliente";
import { Aviso } from "./Aviso";

/** Pergunta ao backend, uma vez, se o app roda com transcrição e correção de exemplo. */
function useModoDemonstracao(): boolean {
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
  return demonstracao;
}

/** Aviso discreto e permanente no topo de todas as telas, no modo de demonstração. */
export function AvisoDemonstracao() {
  const demonstracao = useModoDemonstracao();
  if (!demonstracao) return null;
  return (
    <div className="app-demonstracao">
      <Aviso>Modo de demonstração: a transcrição e a correção são de exemplo.</Aviso>
    </div>
  );
}
