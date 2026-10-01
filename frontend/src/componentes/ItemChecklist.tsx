import type { ReactNode } from "react";
import type { Avaliacao } from "../api/tipos";
import { IconeBandeira, IconeCheck, IconeLampada, IconeX } from "./Icones";

interface Props {
  avaliacao: Avaliacao;
  /** Quem disse o trecho citado ("Você disse", "O paciente disse"). */
  quemFalou: string;
  onContestar?: () => void;
  contestando?: boolean;
  /** Formulário de contestação ou resultado, logo abaixo do item. */
  children?: ReactNode;
}

/** Uma linha da correção: feito (com o trecho que prova) ou faltou (com a pergunta). */
export function ItemChecklist({ avaliacao, quemFalou, onContestar, contestando, children }: Props) {
  const feito = avaliacao.status === "feito";
  return (
    <article className={`al-item ${feito ? "al-item-feito" : "al-item-faltou"}`}>
      <span className="al-item-status">{feito ? <IconeCheck /> : <IconeX />}</span>
      <div className="app-item-corpo">
        <p className="al-item-rotulo">{feito ? "Feito" : "Faltou"}</p>
        <p className="al-item-titulo">{avaliacao.texto}</p>
        {feito ? (
          <>
            {avaliacao.mensagem && avaliacao.mensagem !== avaliacao.texto && (
              <p className="al-item-texto">{avaliacao.mensagem}</p>
            )}
            {avaliacao.trecho && (
              <blockquote className="al-fala">
                <span className="al-fala-quem">{quemFalou}</span>“{avaliacao.trecho}”
              </blockquote>
            )}
          </>
        ) : (
          <p className="al-item-texto">{avaliacao.mensagem}</p>
        )}
        {!avaliacao.conta_na_nota && <p className="app-item-fora">Este item não conta na nota.</p>}
        {onContestar && avaliacao.status === "faltou" && !avaliacao.contestacao && (
          <button
            className="al-contestar app-contestar"
            type="button"
            onClick={onContestar}
            aria-expanded={contestando}
          >
            <IconeBandeira />
            Contestar
          </button>
        )}
        {children}
      </div>
    </article>
  );
}

/** Pergunta sugerida pela IA: fora da nota, não se contesta. */
export function ItemSugestao({ titulo, texto }: { titulo: string; texto?: string }) {
  return (
    <article className="al-item al-item-sugestao">
      <span className="al-item-status">
        <IconeLampada />
      </span>
      <div className="app-item-corpo">
        <p className="al-item-rotulo">Sugestão · fora da nota</p>
        <p className="al-item-titulo">{titulo}</p>
        {texto && <p className="al-item-texto">{texto}</p>}
      </div>
    </article>
  );
}
