import { useSyncExternalStore } from "react";
import { normalizar } from "./formato";

/**
 * Aceites do termo de gravação lembrados neste aparelho.
 *
 * - Dono do perfil: aceita o termo uma vez. O aceite vale para as sessões dele até ser
 *   retirado no Perfil ou até o termo mudar de versão; o app registra o consentimento
 *   dele em cada sessão sem perguntar de novo.
 * - Colega: o app lembra só que aquele nome já leu esta versão do termo, para mostrar a
 *   versão curta. O colega confirma em toda sessão, porque a voz dele também é gravada.
 *
 * O registro por sessão (`consentimentos`, no backend) continua existindo para os dois.
 */
export interface AceiteDono {
  versao: string;
  /** Data e hora do aceite, em ISO. */
  em: string;
}

const CHAVE_DONO = "anamnelab:aceite-termo";
const CHAVE_COLEGAS = "anamnelab:termo-lido";

const ouvintes = new Set<() => void>();
let dono: AceiteDono | null | undefined;

function lerDono(): AceiteDono | null {
  if (dono !== undefined) return dono;
  try {
    const a = JSON.parse(localStorage.getItem(CHAVE_DONO) ?? "null") as Partial<AceiteDono> | null;
    dono = a?.versao && a.em ? { versao: a.versao, em: a.em } : null;
  } catch {
    dono = null;
  }
  return dono;
}

function gravarDono(valor: AceiteDono | null): void {
  dono = valor;
  try {
    if (valor) localStorage.setItem(CHAVE_DONO, JSON.stringify(valor));
    else localStorage.removeItem(CHAVE_DONO);
  } catch {
    // Sem armazenamento, o aceite vale só enquanto o app está aberto.
  }
  ouvintes.forEach((o) => o());
}

export function aceitarComoDono(versao: string): void {
  gravarDono({ versao, em: new Date().toISOString() });
}

export function retirarAceiteDoDono(): void {
  gravarDono(null);
}

export function useAceiteDono(): AceiteDono | null {
  return useSyncExternalStore(
    (o) => {
      ouvintes.add(o);
      return () => ouvintes.delete(o);
    },
    lerDono,
    lerDono,
  );
}

/** O nome digitado no papel é o do dono do perfil? Compara sem acento e sem caixa. */
export function ehDono(nomePapel: string, nomePerfil: string): boolean {
  const a = normalizar(nomePapel);
  return a !== "" && a === normalizar(nomePerfil);
}

function lerColegas(): Record<string, string> {
  try {
    const c = JSON.parse(localStorage.getItem(CHAVE_COLEGAS) ?? "{}") as unknown;
    return c && typeof c === "object" ? (c as Record<string, string>) : {};
  } catch {
    return {};
  }
}

/** Este nome já leu o termo nesta versão, neste aparelho? */
export function colegaJaLeu(nome: string, versao: string): boolean {
  const chave = normalizar(nome);
  return chave !== "" && lerColegas()[chave] === versao;
}

export function lembrarColega(nome: string, versao: string): void {
  const chave = normalizar(nome);
  if (!chave) return;
  try {
    localStorage.setItem(CHAVE_COLEGAS, JSON.stringify({ ...lerColegas(), [chave]: versao }));
  } catch {
    // Sem armazenamento, o termo aparece inteiro de novo.
  }
}
