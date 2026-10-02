import type { ReactNode } from "react";

interface Props {
  /** Nome padrão da lista fechada; duas queixas ligadas por " e ". */
  nome: string;
  /** Fala do paciente que mostra a queixa. */
  trecho?: string | null;
  onConfirmar: () => void;
  onTrocar: () => void;
  confirmando?: boolean;
  children?: ReactNode;
}

/** Pede a confirmação da queixa antes de aplicar o checklist. */
export function QueixaDetectada({ nome, trecho, onConfirmar, onTrocar, confirmando, children }: Props) {
  return (
    <section className="al-queixa app-queixa app-surge" aria-labelledby="queixa-nome">
      <p className="al-queixa-pergunta">Queixa detectada na conversa</p>
      <p className="al-queixa-nome" id="queixa-nome">
        {nome}
      </p>
      <p className="app-legenda">Está certo?</p>
      {trecho && (
        <blockquote className="al-fala app-fala-queixa">
          <span className="al-fala-quem">O paciente disse</span>“{trecho}”
        </blockquote>
      )}
      {children}
      <div className="al-queixa-acoes">
        <button
          className="al-botao al-botao-principal"
          type="button"
          onClick={onConfirmar}
          disabled={confirmando}
        >
          {confirmando ? "Confirmando…" : "Sim, está certo"}
        </button>
        <button className="al-botao al-botao-secundario" type="button" onClick={onTrocar} disabled={confirmando}>
          Trocar
        </button>
      </div>
    </section>
  );
}
