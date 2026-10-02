import { useEffect, useState } from "react";
import { IconeBandeira, IconeCheck } from "./Icones";

interface Props {
  texto: string;
  icone?: "bandeira" | "check";
  onSumir: () => void;
}

/** Recado curto que sobe do rodapé com uma mola leve e desce sozinho. */
export function Recado({ texto, icone = "bandeira", onSumir }: Props) {
  const [saindo, setSaindo] = useState(false);

  useEffect(() => {
    const t = window.setTimeout(() => setSaindo(true), 3600);
    return () => window.clearTimeout(t);
  }, []);

  return (
    <div
      className={`app-recado${saindo ? " is-saindo" : ""}`}
      role="status"
      onAnimationEnd={(e) => {
        if (saindo && e.animationName === "app-recado-sai") onSumir();
      }}
    >
      {icone === "check" ? <IconeCheck /> : <IconeBandeira />}
      {texto}
    </div>
  );
}
