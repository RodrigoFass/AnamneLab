import { IconeCheck } from "./Icones";

export interface Etapa {
  rotulo: string;
  estado: "feita" | "atual" | "pendente";
}

/** Lista de etapas do processamento: o check se desenha quando a etapa termina. */
export function Etapas({ etapas }: { etapas: Etapa[] }) {
  return (
    <ol className="app-etapas" aria-live="polite">
      {etapas.map((e) => (
        <li key={e.rotulo} className={`app-etapa is-${e.estado}`}>
          <span className="app-etapa-marca" aria-hidden="true">
            {e.estado === "feita" && <IconeCheck className="app-check-desenha" />}
          </span>
          <span>{e.rotulo}</span>
          <span className="app-so-leitor">
            {e.estado === "feita" ? ", pronto" : e.estado === "atual" ? ", em andamento" : ", na fila"}
          </span>
        </li>
      ))}
    </ol>
  );
}
