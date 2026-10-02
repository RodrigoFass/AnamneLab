import { useSyncExternalStore } from "react";
import { loginAtivo, supabase } from "../auth/supabase";

/**
 * Perfil do aluno: nome, disciplina, período e avatar. Fica neste aparelho; com login ativo,
 * vai também para os metadados da conta, para aparecer em outro aparelho.
 */
export interface Perfil {
  nome: string;
  disciplina: string;
  periodo: string;
  /** Id de um avatar pronto (componentes/Avatares); vazio usa a inicial do nome. */
  avatar: string;
}

const CHAVE = "anamnelab:perfil";
const VAZIO: Perfil = { nome: "", disciplina: "", periodo: "", avatar: "" };
const ouvintes = new Set<() => void>();
let atual: Perfil | null = null;

function ler(): Perfil {
  if (atual) return atual;
  try {
    const p = JSON.parse(localStorage.getItem(CHAVE) ?? "{}") as Partial<Perfil>;
    atual = { nome: p.nome ?? "", disciplina: p.disciplina ?? "", periodo: p.periodo ?? "", avatar: p.avatar ?? "" };
  } catch {
    atual = VAZIO;
  }
  return atual;
}

export function salvarPerfil(perfil: Perfil, sincronizar = true): void {
  atual = { nome: perfil.nome.trim(), disciplina: perfil.disciplina.trim(), periodo: perfil.periodo, avatar: perfil.avatar };
  try {
    localStorage.setItem(CHAVE, JSON.stringify(atual));
  } catch {
    // Sem armazenamento, o perfil vale só enquanto o app está aberto.
  }
  ouvintes.forEach((o) => o());
  if (sincronizar && loginAtivo) {
    void supabase()
      .then((sb) => sb.auth.updateUser({ data: { perfil: atual } }))
      .catch(() => undefined);
  }
}

/** Adota o perfil da conta quando este aparelho ainda não tem um. */
export function adotarPerfilDaConta(dados: unknown): void {
  const p = (dados as { perfil?: Partial<Perfil> } | null)?.perfil;
  if (!p?.nome || ler().nome) return;
  salvarPerfil({ nome: p.nome, disciplina: p.disciplina ?? "", periodo: p.periodo ?? "", avatar: p.avatar ?? "" }, false);
}

export function usePerfil(): Perfil {
  return useSyncExternalStore(
    (o) => {
      ouvintes.add(o);
      return () => ouvintes.delete(o);
    },
    ler,
    ler,
  );
}

/** "Semiologia · 5º período" */
export function linhaDoPerfil(p: Perfil): string {
  return [p.disciplina, p.periodo ? `${p.periodo} período` : ""].filter(Boolean).join(" · ");
}

export function primeiroNome(nome: string): string {
  return nome.trim().split(/\s+/)[0] ?? "";
}
