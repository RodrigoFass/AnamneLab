import { useSyncExternalStore } from "react";
import { normalizar } from "./formato";

/**
 * Aceite do termo de gravação lembrado neste aparelho.
 *
 * Só o dono do perfil aceita o termo, uma vez. O aceite vale para as sessões dele até ser
 * retirado no Perfil ou até o termo mudar de versão. O colega não aceita no app: o termo do
 * dono traz o compromisso de avisá-lo antes de gravar, e o app registra em cada sessão o
 * aceite do dono e esse aviso (`forma: "declarado_pelo_dono"`).
 */
export interface AceiteDono {
  versao: string;
  /** Data e hora do aceite, em ISO. */
  em: string;
}

const CHAVE_DONO = "anamnelab:aceite-termo";

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
