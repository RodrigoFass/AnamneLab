interface Props {
  valor: number;
  rotulo: string;
}

/** Barra de progresso acessível (trilho linha, preenchimento petróleo). */
export function BarraProgresso({ valor, rotulo }: Props) {
  const v = Math.max(0, Math.min(100, Math.round(valor)));
  return (
    <div
      className="al-barra app-barra-progresso"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={v}
      aria-label={rotulo}
    >
      <span style={{ transform: `scaleX(${v / 100})` }} />
    </div>
  );
}
