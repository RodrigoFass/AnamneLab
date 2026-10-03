import type { ReactNode } from "react";

/** Quantas perguntas e partes do exame, para a folha de encerrar. */
export function resumoDaConsulta(perguntas: number, exames: number): string {
  const p = `${perguntas} ${perguntas === 1 ? "pergunta" : "perguntas"}`;
  const e =
    exames === 0
      ? "e não examinou o paciente"
      : `e examinou ${exames} ${exames === 1 ? "parte" : "partes"} do exame físico`;
  return `Você fez ${p} ${e}. Depois de encerrar, não dá para continuar.`;
}

/** O guia: um preceptor discreto, fora do papel do paciente. */
export function Guia({ children }: { children: ReactNode }) {
  return (
    <p className="app-guia">
      <span className="app-guia-rotulo">Guia</span>
      {children}
    </p>
  );
}

