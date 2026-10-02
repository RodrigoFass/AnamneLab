import { useEffect } from "react";
import { IconeBandeira } from "./Icones";

/** Recado curto que sobe do rodapé e some sozinho. */
export function Recado({ texto, onSumir }: { texto: string; onSumir: () => void }) {
  useEffect(() => {
    const t = window.setTimeout(onSumir, 4000);
    return () => window.clearTimeout(t);
  }, [onSumir]);
  return (
    <div className="app-recado" role="status">
      <IconeBandeira />
      {texto}
    </div>
  );
}
