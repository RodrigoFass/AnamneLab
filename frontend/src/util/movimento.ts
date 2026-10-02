import { useCallback } from "react";
import { useNavigate, type NavigateOptions, type To } from "react-router-dom";
import { lerPreferencias } from "./preferencias";

/** Movimento reduzido no sistema ou nas configurações do app. */
export function movimentoReduzido(): boolean {
  if (lerPreferencias().movimento === "reduzido") return true;
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

/** Vibração curta no toque, onde o aparelho tem (Android). Nunca com movimento reduzido ou desligada. */
export function vibrar(padrao: number | number[]): void {
  if (movimentoReduzido() || !lerPreferencias().vibracao) return;
  try {
    navigator.vibrate?.(padrao);
  } catch {
    // Sem vibração, segue sem.
  }
}

export type Direcao = "avancar" | "voltar" | "aba";

/**
 * Direção da próxima transição entre telas. O CSS lê o atributo no <html>:
 * avançar empurra a tela para a esquerda, voltar faz o contrário, aba só troca.
 */
export function marcarDirecao(direcao: Direcao): void {
  const raiz = document.documentElement;
  raiz.dataset.direcao = direcao;
  window.setTimeout(() => {
    if (raiz.dataset.direcao === direcao) delete raiz.dataset.direcao;
  }, 700);
}

// Voltar do navegador (ou o gesto de voltar do Android) também anima para trás.
window.addEventListener("popstate", () => marcarDirecao("voltar"));

/** navigate() com transição de tela (View Transitions), quando o navegador tem. */
export function useNavegar() {
  const navigate = useNavigate();
  return useCallback(
    (para: To, opcoes: NavigateOptions & { direcao?: Direcao } = {}) => {
      const { direcao = "avancar", ...resto } = opcoes;
      marcarDirecao(direcao);
      navigate(para, { ...resto, viewTransition: !movimentoReduzido() });
    },
    [navigate],
  );
}
