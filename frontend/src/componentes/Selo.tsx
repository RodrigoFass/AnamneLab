import type { ChecklistUsado } from "../api/tipos";
import { IconeSelo } from "./Icones";

/**
 * Status de um checklist. Só dois existem: validado por professor ou rascunho.
 * Rascunho que entra na conta (CONTAR_RASCUNHO=true) diz que a nota é provisória.
 */
export function Selo({ checklist }: { checklist: Pick<ChecklistUsado, "status" | "conta_na_nota"> }) {
  if (checklist.status === "aprovado") {
    return (
      <span className="al-selo al-selo-validado">
        <IconeSelo />
        Validado por professor
      </span>
    );
  }
  return (
    <span className="al-selo al-selo-rascunho">
      {checklist.conta_na_nota ? "Rascunho · nota provisória" : "Rascunho · não conta na nota"}
    </span>
  );
}
