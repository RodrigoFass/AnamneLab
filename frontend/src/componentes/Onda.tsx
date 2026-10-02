import { useEffect, useRef } from "react";

const BARRAS = 35;
const MEIO = (BARRAS - 1) / 2;

/** Altura máxima de cada barra: alta no centro, baixa nas pontas. */
const FORMA = Array.from({ length: BARRAS }, (_, i) => {
  const d = Math.abs(i - MEIO) / MEIO;
  return 0.3 + 0.7 * Math.cos((d * Math.PI) / 2) ** 1.5;
});

/** Faixa de frequência de cada barra: graves no centro, agudos nas pontas, espelhado. */
const FAIXA = Array.from({ length: BARRAS }, (_, i) => Math.round(Math.abs(i - MEIO)));

/**
 * Onda do áudio ao vivo. As barras ficam paradas no lugar e sobem e descem com a voz,
 * espelhadas a partir do centro: o volume dá a altura, e as frequências da fala dão a
 * diferença entre uma barra e outra. Parada, vira uma linha pontilhada. Só lê o volume
 * no aparelho; nada sai daqui.
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
    analisador.smoothingTimeConstant = 0.7;
    fonte.connect(analisador);
    const onda = new Uint8Array(analisador.fftSize);
    const espectro = new Uint8Array(analisador.frequencyBinCount);

    // Faixas da voz (de ~90 Hz a ~4 kHz), em escala logarítmica, uma por distância do centro.
    const larguraBin = ctx.sampleRate / analisador.fftSize;
    const faixas = Math.ceil(MEIO) + 1;
    const limites = Array.from({ length: faixas + 1 }, (_, k) =>
      Math.max(1, Math.round((90 * (4000 / 90) ** (k / faixas)) / larguraBin)),
    );
    const nivelFaixa = new Float32Array(faixas);
    const altura = new Float32Array(BARRAS);
    let quadro = 0;

    const desenhar = () => {
      quadro = requestAnimationFrame(desenhar);
      // Volume pela raiz da média dos quadrados da onda (RMS).
      analisador.getByteTimeDomainData(onda);
      let soma = 0;
      for (const v of onda) soma += ((v - 128) / 128) ** 2;
      const volume = Math.min(1, Math.sqrt(Math.sqrt(soma / onda.length)) * 2.2);

      analisador.getByteFrequencyData(espectro);
      for (let k = 0; k < faixas; k++) {
        const ini = limites[k] ?? 1;
        const fim = Math.max(ini + 1, limites[k + 1] ?? 0);
        let maior = 0;
        for (let b = ini; b < fim && b < espectro.length; b++) maior = Math.max(maior, espectro[b] ?? 0);
        nivelFaixa[k] = maior / 255;
      }

      for (let i = 0; i < BARRAS; i++) {
        const alvo = volume * (FORMA[i] ?? 0) * (0.55 + 0.45 * (nivelFaixa[FAIXA[i] ?? 0] ?? 0));
        // Sobe rápido e desce devagar, como um medidor de nível.
        const antes = altura[i] ?? 0;
        const agora = antes + (alvo - antes) * (alvo > antes ? 0.45 : 0.12);
        altura[i] = agora;
        const b = barras.current[i];
        if (b) b.style.transform = `scaleY(${(0.08 + 0.92 * agora).toFixed(3)})`;
      }
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
          style={{ animationDelay: `${Math.abs(i - MEIO) * 14}ms` }}
          ref={(el) => {
            barras.current[i] = el;
          }}
        />
      ))}
    </div>
  );
}
