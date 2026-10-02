import type { ReactNode } from "react";
import type { Avaliacao } from "../api/tipos";
import { IconeBandeira, IconeCheck, IconeLampada, IconeX } from "./Icones";

interface Props {
  avaliacao: Avaliacao;
  /** Quem disse o trecho citado ("Você disse", "O paciente disse"). */
  quemFalou: string;
  onContestar?: () => void;
  /** Resultado da contestação, logo abaixo do item. */
  children?: ReactNode;
}

/** Uma linha da correção: feito (com o trecho que prova) ou faltou (com a pergunta). */
export function ItemChecklist({ avaliacao, quemFalou, onContestar, children }: Props) {
  const feito = avaliacao.status === "feito";
  const podeContestar = onContestar && avaliacao.status === "faltou" && !avaliacao.contestacao;
  return (
    <article className={`app-item ${feito ? "al-item-feito" : "al-item-faltou"}`}>
      <span className="al-item-status">{feito ? <IconeCheck /> : <IconeX />}</span>
      <div className="app-item-corpo">
        <p className="app-item-titulo">
          <span className="al-item-rotulo">{feito ? "Feito" : "Faltou"}</span>
          <span aria-hidden="true"> · </span>
          {avaliacao.texto}
        </p>
        {feito ? (
          <>
            {/* Com o trecho, a fala já mostra o que foi feito; a frase só aparece sem ele. */}
            {!avaliacao.trecho && avaliacao.mensagem && avaliacao.mensagem !== avaliacao.texto && (
              <p className="al-item-texto">{avaliacao.mensagem}</p>
            )}
            {avaliacao.trecho && (
              <blockquote className="al-fala app-fala">
                <span className="al-fala-quem">{quemFalou}</span>“{avaliacao.trecho}”
              </blockquote>
            )}
          </>
        ) : (
          <p className="al-item-texto">{avaliacao.mensagem}</p>
        )}
        {!avaliacao.conta_na_nota && <p className="app-item-fora">Este item não conta na nota.</p>}
        {children}
      </div>
      {podeContestar && (
        <button
          className="app-item-bandeira"
          type="button"
          onClick={onContestar}
          aria-label={`Contestar: ${avaliacao.texto}`}
          title="Contestar"
        >
          <IconeBandeira />
        </button>
      )}
    </article>
  );
}

/** Pergunta sugerida pela IA: fora da nota, não se contesta. */
export function ItemSugestao({ titulo, texto }: { titulo: string; texto?: string }) {
  return (
    <article className="app-sugestao">
      <p className="app-sugestao-rotulo">
        <IconeLampada />
        Sugestão, fora da nota
      </p>
      <p>{titulo}</p>
      {texto && <p className="app-legenda">{texto}</p>}
    </article>
  );
}
