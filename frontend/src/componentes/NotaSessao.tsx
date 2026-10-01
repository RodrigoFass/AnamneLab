interface BlocoNota {
  rotulo: string;
  nota: number | null;
  /** Linha de contexto: o que faltou, ou por que não há nota. */
  meta: string;
}

function Bloco({ rotulo, nota, meta }: BlocoNota) {
  return (
    <section className="al-nota-bloco">
      <p className="al-nota-rotulo">{rotulo}</p>
      {nota === null ? (
        <>
          <p className="al-nota-numero app-sem-nota">Sem nota</p>
          <p className="al-nota-meta">{meta}</p>
        </>
      ) : (
        <>
          <p className="al-nota-numero">
            {nota}
            <small> /100</small>
          </p>
          <div className="al-barra" role="img" aria-label={`${nota} de 100`}>
            <span style={{ transform: `scaleX(${Math.max(0, Math.min(100, nota)) / 100})` }} />
          </div>
          <p className="al-nota-meta">{meta}</p>
        </>
      )}
    </section>
  );
}

interface Props {
  geral: BlocoNota;
  queixa: BlocoNota;
}

/** As duas notas lado a lado, nunca somadas. A barra é sempre petróleo. */
export function NotaSessao({ geral, queixa }: Props) {
  return (
    <div className="al-nota app-nota">
      <Bloco {...geral} />
      <Bloco {...queixa} />
    </div>
  );
}
