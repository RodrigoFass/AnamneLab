import type { Cartao } from "../api/tipos";
import { IconeDado } from "./Icones";

function quem(c: Cartao): string {
  return `${c.idade} anos, ${c.sexo === "feminino" ? "mulher" : "homem"}`;
}

interface Props {
  cartao: Cartao;
  /** Nome de quem faz o paciente, para a linha final. */
  nomePaciente?: string;
  onSortearOutro?: () => void;
  sorteando?: boolean;
}

/** Cartão sorteado: ponto de partida para quem faz o paciente. Sem gabarito. */
export function CartaoPaciente({ cartao, nomePaciente, onSortearOutro, sorteando }: Props) {
  return (
    <section className="al-cartao app-cartao" aria-label="Cartão do paciente">
      <div className="al-cartao-topo">
        <span className="al-cartao-tag">
          <IconeDado />
          Cartão de paciente
        </span>
        {onSortearOutro && (
          <button
            className="al-botao al-botao-texto"
            type="button"
            onClick={onSortearOutro}
            disabled={sorteando}
          >
            {sorteando ? "Sorteando…" : "Sortear outro"}
          </button>
        )}
      </div>
      <p className="al-cartao-quem">{quem(cartao)}</p>
      <p className="al-cartao-queixa">{cartao.resumo}</p>
      {cartao.detalhes.length > 0 && (
        <ul className="app-cartao-detalhes">
          {cartao.detalhes.map((d) => (
            <li key={d}>{d}</li>
          ))}
        </ul>
      )}
      <p className="al-cartao-nota">
        Sem gabarito. O resto, {nomePaciente || "você"} improvisa. Responda só o que perguntarem.
      </p>
    </section>
  );
}
