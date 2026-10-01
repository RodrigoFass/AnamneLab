import type { ReactNode } from "react";
import { IconeAviso } from "./Icones";

interface Props {
  children: ReactNode;
  tipo?: "info" | "erro";
  titulo?: string;
}

/** Aviso com ícone e palavra. Erro usa a cor de faltou, nunca a de gravar. */
export function Aviso({ children, tipo = "info", titulo }: Props) {
  return (
    <div className={`app-aviso app-aviso-${tipo}`} role={tipo === "erro" ? "alert" : "note"}>
      <IconeAviso />
      <div>
        {titulo && <p className="app-aviso-titulo">{titulo}</p>}
        <div className="app-aviso-texto">{children}</div>
      </div>
    </div>
  );
}
