/** Linha de notas, da mais antiga para a mais nova. A linha se desenha ao aparecer. */
export function LinhaNotas({ notas, largura = 120, altura = 40 }: { notas: number[]; largura?: number; altura?: number }) {
  if (notas.length < 2) return null;
  const min = Math.min(...notas, 40);
  const max = Math.max(...notas, 100);
  const x = (i: number) => 4 + (i * (largura - 8)) / (notas.length - 1);
  const y = (n: number) => altura - 4 - ((n - min) / (max - min || 1)) * (altura - 8);
  const d = notas.map((n, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)} ${y(n).toFixed(1)}`).join(" ");
  const ultimo = notas.length - 1;
  return (
    <svg
      className="app-linha-notas"
      width={largura}
      height={altura}
      viewBox={`0 0 ${largura} ${altura}`}
      role="img"
      aria-label={`Notas de técnica geral nas últimas sessões: ${notas.join(", ")}`}
    >
      <path className="app-linha-traco" d={d} pathLength={1} />
      <circle className="app-linha-ponto" cx={x(ultimo)} cy={y(notas[ultimo] ?? 0)} r={3.5} />
    </svg>
  );
}
