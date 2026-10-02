import type { Papel } from "../api/tipos";

/** Inicial do nome num círculo: petróleo para quem faz o médico, mostarda para o paciente. */
export function Avatar({ nome, papel, tamanho = 32 }: { nome: string; papel: Papel; tamanho?: number }) {
  const inicial = nome.trim().charAt(0).toUpperCase() || (papel === "medico" ? "M" : "P");
  return (
    <span
      className={`app-avatar app-avatar-${papel}`}
      style={{ width: tamanho, height: tamanho, fontSize: Math.round(tamanho * 0.42) }}
      aria-hidden="true"
    >
      {inicial}
    </span>
  );
}
