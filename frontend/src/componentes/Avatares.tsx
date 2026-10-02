/**
 * Avatares prontos: estudantes de jaleco, desenhados aqui mesmo em SVG (sem foto, sem
 * download). O id fica no perfil; id vazio ou desconhecido volta para a inicial do nome.
 */

type Cabelo = "curto" | "raspado" | "longo" | "coque" | "cacheado" | "lenco";

interface Desenho {
  fundo: string;
  pele: string;
  cabelo: Cabelo;
  corCabelo: string;
  oculos?: boolean;
  estetoscopio?: boolean;
}

const PELE = { clara: "#F2D3B8", media: "#E0B48F", morena: "#B9825A", escura: "#7A4E33" };
const CABELO = { escuro: "#2B211C", castanho: "#6B4428", dourado: "#C98B3E", grisalho: "#8E9296", ruivo: "#A4492A" };
const FUNDO = { petroleo: "#CFE3E2", mostarda: "#F3DDA8", argila: "#EBD5C8", salvia: "#D6E3D1", areia: "#E6E0D2" };

export const AVATARES: { id: string; rotulo: string; desenho: Desenho }[] = [
  { id: "a1", rotulo: "Cabelo curto escuro", desenho: { fundo: FUNDO.petroleo, pele: PELE.media, cabelo: "curto", corCabelo: CABELO.escuro, estetoscopio: true } },
  { id: "a2", rotulo: "Cabelo longo castanho", desenho: { fundo: FUNDO.mostarda, pele: PELE.clara, cabelo: "longo", corCabelo: CABELO.castanho } },
  { id: "a3", rotulo: "Cabelo cacheado", desenho: { fundo: FUNDO.salvia, pele: PELE.escura, cabelo: "cacheado", corCabelo: CABELO.escuro, estetoscopio: true } },
  { id: "a4", rotulo: "Coque e óculos", desenho: { fundo: FUNDO.argila, pele: PELE.morena, cabelo: "coque", corCabelo: CABELO.escuro, oculos: true } },
  { id: "a5", rotulo: "Cabelo raspado", desenho: { fundo: FUNDO.areia, pele: PELE.escura, cabelo: "raspado", corCabelo: CABELO.escuro } },
  { id: "a6", rotulo: "Lenço", desenho: { fundo: FUNDO.petroleo, pele: PELE.media, cabelo: "lenco", corCabelo: "#0E5E66", estetoscopio: true } },
  { id: "a7", rotulo: "Cabelo longo ruivo", desenho: { fundo: FUNDO.salvia, pele: PELE.clara, cabelo: "longo", corCabelo: CABELO.ruivo, oculos: true } },
  { id: "a8", rotulo: "Cabelo curto dourado", desenho: { fundo: FUNDO.mostarda, pele: PELE.clara, cabelo: "curto", corCabelo: CABELO.dourado } },
  { id: "a9", rotulo: "Cabelo cacheado castanho", desenho: { fundo: FUNDO.argila, pele: PELE.morena, cabelo: "cacheado", corCabelo: CABELO.castanho } },
  { id: "a10", rotulo: "Cabelo grisalho e óculos", desenho: { fundo: FUNDO.areia, pele: PELE.media, cabelo: "curto", corCabelo: CABELO.grisalho, oculos: true, estetoscopio: true } },
  { id: "a11", rotulo: "Coque castanho", desenho: { fundo: FUNDO.petroleo, pele: PELE.escura, cabelo: "coque", corCabelo: CABELO.castanho } },
  { id: "a12", rotulo: "Cabelo longo escuro e óculos", desenho: { fundo: FUNDO.argila, pele: PELE.morena, cabelo: "longo", corCabelo: CABELO.escuro, oculos: true, estetoscopio: true } },
];

export function avatarExiste(id: string | undefined): boolean {
  return !!id && AVATARES.some((a) => a.id === id);
}

const TRACO = "#1F2A2C";
const FRANJA = "M21 27 C20 17 26 13 32 13 C39 13 44 17 43 27 C41 21 36 19 32 19 C27 19 23 21 21 27 Z";

function CabeloAtras({ d }: { d: Desenho }) {
  if (d.cabelo === "longo") {
    return <path d="M19 28 C18 15 25 11 32 11 C39 11 46 15 45 28 L46 47 L18 47 Z" fill={d.corCabelo} />;
  }
  if (d.cabelo === "lenco") {
    return <path d="M17 31 C17 16 24 10 32 10 C40 10 47 16 47 31 L50 50 L14 50 Z" fill={d.corCabelo} />;
  }
  if (d.cabelo === "coque") return <circle cx="32" cy="11" r="5.5" fill={d.corCabelo} />;
  return null;
}

function CabeloFrente({ d }: { d: Desenho }) {
  switch (d.cabelo) {
    case "curto":
    case "longo":
    case "coque":
      return <path d={FRANJA} fill={d.corCabelo} />;
    case "raspado":
      return (
        <path
          d="M21.5 25 C22 17 27 15.5 32 15.5 C37 15.5 42 17 42.5 25 C40 20 36 19 32 19 C28 19 24 20 21.5 25 Z"
          fill={d.corCabelo}
        />
      );
    case "cacheado":
      return (
        <g fill={d.corCabelo}>
          <path d={FRANJA} />
          <circle cx="21.5" cy="23" r="4.5" />
          <circle cx="25" cy="16.5" r="5" />
          <circle cx="32" cy="14" r="5.5" />
          <circle cx="39" cy="16.5" r="5" />
          <circle cx="42.5" cy="23" r="4.5" />
        </g>
      );
    case "lenco":
      return null;
  }
}

/** O desenho ocupa um quadrado 64 x 64; quem usa decide o tamanho. */
export function DesenhoAvatar({ id }: { id: string }) {
  const d = AVATARES.find((a) => a.id === id)?.desenho;
  if (!d) return null;
  const lenco = d.cabelo === "lenco";
  return (
    <svg viewBox="0 0 64 64" width="100%" height="100%" aria-hidden="true" focusable="false">
      <circle cx="32" cy="32" r="32" fill={d.fundo} />
      <CabeloAtras d={d} />
      {/* jaleco, com a gola do pijama cirúrgico */}
      <path d="M11 64 C11 51 21 44.5 32 44.5 C43 44.5 53 51 53 64 Z" fill="#FFFFFF" />
      <path d="M26.5 45.2 L32 55 L37.5 45.2 Z" fill="#0E5E66" />
      <path d="M26.5 45.2 L30 58 M37.5 45.2 L34 58" stroke="#D5D9DA" strokeWidth="1.2" fill="none" />
      <rect x="28" y="35" width="8" height="11" rx="3" fill={d.pele} />
      <rect x="28" y="35" width="8" height="4" fill="#000" opacity="0.08" />
      <ellipse cx="32" cy="28" rx={lenco ? 9.5 : 11} ry={lenco ? 11 : 12} fill={d.pele} />
      <CabeloFrente d={d} />
      <circle cx="28" cy="29" r="1.4" fill={TRACO} />
      <circle cx="36" cy="29" r="1.4" fill={TRACO} />
      <path d="M28.5 34 Q32 37 35.5 34" stroke={TRACO} strokeWidth="1.5" strokeLinecap="round" fill="none" />
      {d.oculos && (
        <g stroke={TRACO} strokeWidth="1.2" fill="none">
          <circle cx="28" cy="29" r="3.4" />
          <circle cx="36" cy="29" r="3.4" />
          <path d="M31.4 29 H32.6" />
        </g>
      )}
      {d.estetoscopio && (
        <g stroke="#55636A" strokeWidth="1.6" fill="none" strokeLinecap="round">
          <path d="M24.5 46 C24 53 27.5 57 31 57.5" />
          <path d="M39.5 46 C40 51 39 54 37.5 55.5" />
          <circle cx="37" cy="57" r="2" fill="#55636A" />
        </g>
      )}
    </svg>
  );
}
