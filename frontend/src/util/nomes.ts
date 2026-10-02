import type { Consentimento, OrigemCaso, Papel } from "../api/tipos";

/**
 * Nomes de quem faz cada papel, digitados na nova sessão e usados no termo.
 * Ficam só nesta aba do navegador; o que vale é o nome informado no aceite.
 */
export type Nomes = Record<Papel, string>;

const CHAVE = "anamnelab:nomes";

export function lerNomes(): Nomes {
  try {
    const n = JSON.parse(sessionStorage.getItem(CHAVE) ?? "{}") as Partial<Nomes>;
    return { medico: n.medico ?? "", paciente: n.paciente ?? "" };
  } catch {
    return { medico: "", paciente: "" };
  }
}

export function guardarNomes(nomes: Nomes): void {
  try {
    sessionStorage.setItem(CHAVE, JSON.stringify(nomes));
  } catch {
    // Sem armazenamento, o termo pede os nomes de novo.
  }
}

/** Nome registrado no aceite de cada papel. */
export function nomesDaSessao(consentimentos: Consentimento[]): Nomes {
  const de = (p: Papel) => consentimentos.find((c) => c.papel === p)?.nome_informado ?? "";
  return { medico: de("medico"), paciente: de("paciente") };
}

export const ROTULO_ORIGEM: Record<OrigemCaso, string> = {
  livro: "caso de livro",
  internet: "caso da internet",
  inventado: "caso inventado",
  cartao: "cartão sorteado",
};

/** "Ana e Pedro · cartão sorteado" */
export function linhaDaDupla(consentimentos: Consentimento[], origem: OrigemCaso): string {
  const n = nomesDaSessao(consentimentos);
  const dupla = [n.medico, n.paciente].filter(Boolean).join(" e ");
  return dupla ? `${dupla} · ${ROTULO_ORIGEM[origem]}` : ROTULO_ORIGEM[origem];
}
