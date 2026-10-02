import type { MouseEvent, PointerEvent } from "react";
import { IconeArco, IconeMicrofone, IconeQuadrado } from "./Icones";

export type EstadoBotaoGravar = "pronto" | "gravando" | "processando";

interface Props {
  estado: EstadoBotaoGravar;
  /** Tempo gravado; a tela mostra o cronômetro grande. */
  segundos: number;
  legendaProcessando?: string;
  onAlternar: () => void;
  desativado?: boolean;
}

/**
 * Botão redondo de gravar. Responde no pointerdown, não no soltar: o aluno vê na hora
 * que a gravação começou. Teclado e leitor de tela chegam pelo clique sem ponteiro.
 */
export function BotaoGravar({ estado, legendaProcessando, onAlternar, desativado }: Props) {
  const gravando = estado === "gravando";
  const processando = estado === "processando";

  const aoPressionar = (e: PointerEvent<HTMLButtonElement>) => {
    if (desativado || processando) return;
    if (e.pointerType === "mouse" && e.button !== 0) return;
    e.preventDefault();
    onAlternar();
  };
  // Clique sem ponteiro (detail 0) vem do teclado ou de leitor de tela.
  const aoClicar = (e: MouseEvent<HTMLButtonElement>) => {
    if (e.detail === 0 && !desativado && !processando) onAlternar();
  };

  const rotulo = processando
    ? "Processando a gravação"
    : gravando
      ? "Parar a gravação"
      : "Começar a gravação";

  return (
    <div className={`al-gravar-bloco app-gravar-bloco${gravando ? " is-gravando" : ""}`}>
      <span className="app-gravar-aneis" aria-hidden="true" />
      <button
        className={`al-gravar${gravando ? " is-gravando" : ""}${processando ? " is-processando" : ""}`}
        type="button"
        aria-label={rotulo}
        aria-busy={processando || undefined}
        disabled={desativado}
        onPointerDown={aoPressionar}
        onClick={aoClicar}
      >
        {processando ? <IconeArco className="app-girando" /> : gravando ? <IconeQuadrado /> : <IconeMicrofone />}
      </button>
      <span className="app-so-leitor" aria-live="polite">
        {gravando ? "Gravando" : processando ? (legendaProcessando ?? "Processando") : ""}
      </span>
      <span className="al-gravar-tempo app-gravar-tempo">
        {processando ? (legendaProcessando ?? "Processando…") : gravando ? "Toque para parar" : "Toque para gravar"}
      </span>
    </div>
  );
}
