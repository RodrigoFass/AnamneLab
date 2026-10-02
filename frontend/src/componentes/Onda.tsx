import { useEffect, useRef } from "react";

const BARRAS = 36;
/** Uma barra nova a cada 70 ms: a onda anda da direita para a esquerda, como num gravador. */
const PASSO_MS = 70;

/**
 * Onda do áudio ao vivo: cada barra é o volume do microfone num instante. Parada,
 * vira uma linha pontilhada. Só lê o volume no aparelho; nada sai daqui.
 */
export function Onda({ fluxo }: { fluxo: MediaStream | null }) {
  const barras = useRef<(HTMLSpanElement | null)[]>([]);

  useEffect(() => {
    if (!fluxo) return;
    const Contexto =
      window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Contexto) return;
    const ctx = new Contexto();
    // Alguns navegadores criam o contexto suspenso fora do toque; o volume só chega depois do resume.
    void ctx.resume().catch(() => undefined);
    const fonte = ctx.createMediaStreamSource(fluxo);
    const analisador = ctx.createAnalyser();
    analisador.fftSize = 512;
    fonte.connect(analisador);
    const dados = new Uint8Array(analisador.fftSize);
    const historico: number[] = Array(BARRAS).fill(0);
    let quadro = 0;
    let ultimo = 0;

    const desenhar = (agora: number) => {
      quadro = requestAnimationFrame(desenhar);
      if (agora - ultimo < PASSO_MS) return;
      ultimo = agora;
      // Volume pela raiz da média dos quadrados da onda (RMS).
      analisador.getByteTimeDomainData(dados);
      let soma = 0;
      for (const v of dados) soma += ((v - 128) / 128) ** 2;
      const rms = Math.sqrt(soma / dados.length);
      // Um pouco de variação por barra, para a fala não virar um bloco só.
      const volume = Math.min(1, Math.sqrt(rms) * 2.2) * (0.7 + 0.3 * Math.random());
      historico.shift();
      historico.push(volume);
      historico.forEach((v, i) => {
        const b = barras.current[i];
        if (b) b.style.transform = `scaleY(${(0.1 + 0.9 * v).toFixed(3)})`;
      });
    };
    quadro = requestAnimationFrame(desenhar);

    return () => {
      cancelAnimationFrame(quadro);
      fonte.disconnect();
      void ctx.close();
    };
  }, [fluxo]);

  if (!fluxo) return <div className="app-onda is-parada" aria-hidden="true" />;

  return (
    <div className="app-onda" aria-hidden="true">
      {Array.from({ length: BARRAS }, (_, i) => (
        <span
          key={i}
          ref={(el) => {
            barras.current[i] = el;
          }}
        />
      ))}
    </div>
  );
}
