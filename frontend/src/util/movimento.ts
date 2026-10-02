import { useEffect, useState } from "react";

export function movimentoReduzido(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

/** Conta de 0 até o alvo, desacelerando no fim. Com movimento reduzido, mostra o alvo direto. */
export function useContagem(alvo: number | null, duracaoMs = 900): number | null {
  const [valor, setValor] = useState<number | null>(alvo === null || movimentoReduzido() ? alvo : 0);

  useEffect(() => {
    if (alvo === null || movimentoReduzido()) {
      setValor(alvo);
      return;
    }
    let quadro = 0;
    const inicio = performance.now();
    const passo = (agora: number) => {
      const t = Math.min(1, (agora - inicio) / duracaoMs);
      const suave = 1 - Math.pow(1 - t, 3);
      setValor(Math.round(alvo * suave));
      if (t < 1) quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro);
  }, [alvo, duracaoMs]);

  return valor;
}
