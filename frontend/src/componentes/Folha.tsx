import { useEffect, useRef, type ReactNode } from "react";

interface Props {
  titulo: string;
  subtitulo?: string;
  onFechar: () => void;
  children: ReactNode;
}

/**
 * Folha que sobe de baixo, sobre um véu. Esc ou toque no véu fecha. Sai pelo
 * mesmo caminho em que entrou (guia da marca, Movimento).
 */
export function Folha({ titulo, subtitulo, onFechar, children }: Props) {
  const caixa = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const anterior = document.activeElement as HTMLElement | null;
    caixa.current?.focus();
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === "Escape") onFechar();
    };
    document.addEventListener("keydown", aoTeclar);
    document.body.classList.add("app-sem-rolagem");
    return () => {
      document.removeEventListener("keydown", aoTeclar);
      document.body.classList.remove("app-sem-rolagem");
      anterior?.focus?.();
    };
  }, [onFechar]);

  return (
    <div className="app-folha-fundo" onClick={onFechar}>
      <div
        ref={caixa}
        className="app-folha"
        role="dialog"
        aria-modal="true"
        aria-labelledby="folha-titulo"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <span className="app-folha-alca" aria-hidden="true" />
        <h2 className="app-folha-titulo" id="folha-titulo">
          {titulo}
        </h2>
        {subtitulo && <p className="app-legenda">{subtitulo}</p>}
        <div className="app-folha-corpo">{children}</div>
      </div>
    </div>
  );
}
