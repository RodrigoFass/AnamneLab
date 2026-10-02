import { Contador } from "./Contador";

interface Ponto {
  nota: number;
  rotulo: string;
}

const L = 320;
const A = 168;
const M = { esq: 30, dir: 14, topo: 26, base: 24 };
const EIXO = [40, 60, 80, 100];

/**
 * Gráfico da técnica geral nas últimas sessões. A linha se desenha da esquerda para
 * a direita, os pontos aparecem em sequência e a última nota ganha a etiqueta.
 */
export function GraficoEvolucao({ pontos }: { pontos: Ponto[] }) {
  const min = Math.min(40, ...pontos.map((p) => p.nota));
  const max = 100;
  const largura = L - M.esq - M.dir;
  const altura = A - M.topo - M.base;
  const x = (i: number) => M.esq + (pontos.length === 1 ? largura : (i * largura) / (pontos.length - 1));
  const y = (n: number) => M.topo + altura - ((n - min) / (max - min)) * altura;
  const d = pontos.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)} ${y(p.nota).toFixed(1)}`).join(" ");
  const ultimo = pontos[pontos.length - 1];
  const descricao = pontos.map((p) => `${p.rotulo}: ${p.nota}`).join(", ");

  return (
    <figure className="app-grafico">
      <svg viewBox={`0 0 ${L} ${A}`} role="img" aria-label={`Técnica geral por sessão. ${descricao}.`}>
        {EIXO.filter((v) => v >= min).map((v) => (
          <g key={v} className="app-grafico-eixo">
            <line x1={M.esq} x2={L - M.dir} y1={y(v)} y2={y(v)} />
            <text x={M.esq - 8} y={y(v) + 4} textAnchor="end">
              {v}
            </text>
          </g>
        ))}
        {pontos.map((p, i) => (
          <text key={i} className="app-grafico-rotulo" x={x(i)} y={A - 6} textAnchor="middle">
            {p.rotulo}
          </text>
        ))}
        <path className="app-grafico-linha" d={d} pathLength={1} />
        {pontos.map((p, i) => (
          <circle
            key={i}
            className={`app-grafico-ponto${i === pontos.length - 1 ? " is-ultimo" : ""}`}
            cx={x(i)}
            cy={y(p.nota)}
            r={i === pontos.length - 1 ? 5 : 3.5}
            style={{ animationDelay: `${300 + (i * 700) / Math.max(1, pontos.length - 1)}ms` }}
          />
        ))}
      </svg>
      {ultimo && (
        <span
          className="app-grafico-etiqueta"
          style={{ left: `${(x(pontos.length - 1) / L) * 100}%`, top: `${(y(ultimo.nota) / A) * 100}%` }}
          aria-hidden="true"
        >
          <Contador texto={String(ultimo.nota)} doZero />
        </span>
      )}
    </figure>
  );
}
