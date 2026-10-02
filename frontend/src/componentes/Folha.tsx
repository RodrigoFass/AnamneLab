import { useCallback, useEffect, useRef, useState, type PointerEvent, type ReactNode } from "react";
import { movimentoReduzido } from "../util/movimento";

interface Props {
  titulo: string;
  subtitulo?: string;
  onFechar: () => void;
  children: ReactNode;
}

/** Quanto puxar para baixo (px), ou com que velocidade (px/ms), para a folha fechar. */
const DISTANCIA_FECHAR = 110;
const VELOCIDADE_FECHAR = 0.55;

/**
 * Folha que sobe de baixo, sobre um véu. Fecha com Esc, com toque no véu ou puxando
 * pela alça; puxada até a metade, volta com mola. Sai pelo mesmo caminho em que entrou.
 */
export function Folha({ titulo, subtitulo, onFechar, children }: Props) {
  const caixa = useRef<HTMLDivElement>(null);
  const arrasto = useRef<{ y0: number; t0: number; dy: number; ultimoY: number; ultimoT: number } | null>(null);
  const [saindo, setSaindo] = useState(false);
  const [puxando, setPuxando] = useState(0);

  const fechar = useCallback(() => {
    if (movimentoReduzido()) onFechar();
    else setSaindo(true);
  }, [onFechar]);

  useEffect(() => {
    const anterior = document.activeElement as HTMLElement | null;
    caixa.current?.focus();
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === "Escape") fechar();
    };
    document.addEventListener("keydown", aoTeclar);
    document.body.classList.add("app-sem-rolagem");
    return () => {
      document.removeEventListener("keydown", aoTeclar);
      document.body.classList.remove("app-sem-rolagem");
      anterior?.focus?.();
    };
  }, [fechar]);

  const aoPressionar = (e: PointerEvent<HTMLDivElement>) => {
    if (saindo) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    arrasto.current = { y0: e.clientY, t0: e.timeStamp, dy: 0, ultimoY: e.clientY, ultimoT: e.timeStamp };
  };
  const aoMover = (e: PointerEvent<HTMLDivElement>) => {
    const a = arrasto.current;
    if (!a) return;
    const dy = e.clientY - a.y0;
    // Para cima, resiste (elástico); para baixo, segue o dedo.
    a.dy = dy < 0 ? dy * 0.15 : dy;
    a.ultimoY = e.clientY;
    a.ultimoT = e.timeStamp;
    setPuxando(a.dy);
  };
  const aoSoltar = (e: PointerEvent<HTMLDivElement>) => {
    const a = arrasto.current;
    arrasto.current = null;
    if (!a) return;
    const tempo = Math.max(1, e.timeStamp - a.t0);
    const velocidade = a.dy / tempo;
    // Ao fechar, a folha desce de onde o dedo largou; senão, volta com mola.
    if (a.dy > DISTANCIA_FECHAR || velocidade > VELOCIDADE_FECHAR) fechar();
    else setPuxando(0);
  };

  const estilo = puxando ? { transform: `translateY(${puxando}px)`, transition: "none" } : undefined;

  return (
    <div
      className={`app-folha-fundo${saindo ? " is-saindo" : ""}`}
      onClick={fechar}
      style={puxando > 0 ? { opacity: Math.max(0.3, 1 - puxando / 400) } : undefined}
    >
      <div
        ref={caixa}
        className="app-folha"
        role="dialog"
        aria-modal="true"
        aria-labelledby="folha-titulo"
        tabIndex={-1}
        style={estilo}
        onClick={(e) => e.stopPropagation()}
        onAnimationEnd={(e) => {
          if (saindo && e.animationName === "app-folha-desce") onFechar();
        }}
      >
        <div
          className="app-folha-pega"
          onPointerDown={aoPressionar}
          onPointerMove={aoMover}
          onPointerUp={aoSoltar}
          onPointerCancel={aoSoltar}
        >
          <span className="app-folha-alca" aria-hidden="true" />
          <h2 className="app-folha-titulo" id="folha-titulo">
            {titulo}
          </h2>
          {subtitulo && <p className="app-legenda">{subtitulo}</p>}
        </div>
        <div className="app-folha-corpo">{children}</div>
      </div>
    </div>
  );
}
