import { useSyncExternalStore } from "react";

/** Configurações do app escolhidas pelo aluno. Ficam neste aparelho. */
export interface Preferencias {
  /** "automatico" segue o tema do sistema. */
  tema: "automatico" | "claro" | "escuro";
  texto: "normal" | "grande" | "maior";
  /** "automatico" segue o "reduzir movimento" do sistema. */
  movimento: "automatico" | "reduzido";
  vibracao: boolean;
}

export const PADRAO: Preferencias = {
  tema: "automatico",
  texto: "normal",
  movimento: "automatico",
  vibracao: true,
};

const CHAVE = "anamnelab:preferencias";
const ouvintes = new Set<() => void>();
let atual: Preferencias | undefined;

function um<T extends string>(valor: unknown, opcoes: readonly T[], padrao: T): T {
  return opcoes.includes(valor as T) ? (valor as T) : padrao;
}

export function lerPreferencias(): Preferencias {
  if (atual) return atual;
  try {
    const p = JSON.parse(localStorage.getItem(CHAVE) ?? "{}") as Partial<Preferencias>;
    atual = {
      tema: um(p.tema, ["automatico", "claro", "escuro"], PADRAO.tema),
      texto: um(p.texto, ["normal", "grande", "maior"], PADRAO.texto),
      movimento: um(p.movimento, ["automatico", "reduzido"], PADRAO.movimento),
      vibracao: typeof p.vibracao === "boolean" ? p.vibracao : PADRAO.vibracao,
    };
  } catch {
    atual = PADRAO;
  }
  return atual;
}

export function salvarPreferencias(mudanca: Partial<Preferencias>): void {
  atual = { ...lerPreferencias(), ...mudanca };
  try {
    localStorage.setItem(CHAVE, JSON.stringify(atual));
  } catch {
    // Sem armazenamento (aba anônima): vale até fechar o app.
  }
  for (const ouvinte of ouvintes) ouvinte();
}

function assinar(ouvinte: () => void): () => void {
  ouvintes.add(ouvinte);
  return () => ouvintes.delete(ouvinte);
}

export function usePreferencias(): Preferencias {
  return useSyncExternalStore(assinar, lerPreferencias, lerPreferencias);
}
