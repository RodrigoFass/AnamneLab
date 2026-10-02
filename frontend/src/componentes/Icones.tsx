// Ícones de traço 2px, grade de 24px, pontas arredondadas (classe al-icone).
// Significados fixos da marca: microfone (gravar), quadrado (parar), check (feito),
// x (faltou), lâmpada (sugestão), bandeira (contestar), selo (validado), dado (cartão).
import type { ReactNode } from "react";

function Svg({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <svg
      className={className ? `al-icone ${className}` : "al-icone"}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

interface P {
  className?: string;
}

export const IconeMicrofone = ({ className }: P) => (
  <Svg className={className}>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0" />
    <path d="M12 18v3" />
  </Svg>
);

export const IconeQuadrado = ({ className }: P) => (
  <Svg className={className}>
    <rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" stroke="none" />
  </Svg>
);

export const IconeCheck = ({ className }: P) => (
  <Svg className={className}>
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </Svg>
);

export const IconeX = ({ className }: P) => (
  <Svg className={className}>
    <path d="M6 6l12 12M18 6L6 18" />
  </Svg>
);

export const IconeLampada = ({ className }: P) => (
  <Svg className={className}>
    <path d="M9 18h6M10 21h4" />
    <path d="M12 3a6 6 0 0 0-3.6 10.8c.7.6 1.1 1.3 1.1 2.2h5c0-.9.4-1.6 1.1-2.2A6 6 0 0 0 12 3z" />
  </Svg>
);

export const IconeBandeira = ({ className }: P) => (
  <Svg className={className}>
    <path d="M5 21V4" />
    <path d="M5 4h12l-2.5 4L17 12H5" />
  </Svg>
);

export const IconeSelo = ({ className }: P) => (
  <Svg className={className}>
    <circle cx="12" cy="12" r="9" />
    <path d="M8.5 12.3l2.4 2.4 4.6-4.9" />
  </Svg>
);

export const IconeDado = ({ className }: P) => (
  <Svg className={className}>
    <rect x="4" y="4" width="16" height="16" rx="3" />
    <circle cx="9" cy="9" r="1.2" fill="currentColor" />
    <circle cx="15" cy="9" r="1.2" fill="currentColor" />
    <circle cx="9" cy="15" r="1.2" fill="currentColor" />
    <circle cx="15" cy="15" r="1.2" fill="currentColor" />
  </Svg>
);

/** Arco do estado "processando". */
export const IconeArco = ({ className }: P) => (
  <Svg className={className}>
    <path d="M12 3a9 9 0 1 0 9 9" />
  </Svg>
);

/** Círculo com ponto de exclamação: avisos e erros (nunca usa a cor de gravar). */
export const IconeAviso = ({ className }: P) => (
  <Svg className={className}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7.5v5.5" />
    <path d="M12 16.5h.01" />
  </Svg>
);

export const IconeVoltar = ({ className }: P) => (
  <Svg className={className}>
    <path d="M15 5l-7 7 7 7" />
  </Svg>
);

export const IconeMais = ({ className }: P) => (
  <Svg className={className}>
    <path d="M12 5v14M5 12h14" />
  </Svg>
);

export const IconeLivro = ({ className }: P) => (
  <Svg className={className}>
    <path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5z" />
    <path d="M5 19.5A1.5 1.5 0 0 0 6.5 21H19v-3" />
  </Svg>
);

export const IconeGlobo = ({ className }: P) => (
  <Svg className={className}>
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12h18" />
    <path d="M12 3a14 14 0 0 1 0 18a14 14 0 0 1 0-18z" />
  </Svg>
);

export const IconeLapis = ({ className }: P) => (
  <Svg className={className}>
    <path d="M4 20l1-4L16.5 4.5a2.1 2.1 0 0 1 3 3L8 19z" />
    <path d="M14.5 6.5l3 3" />
  </Svg>
);

export const IconeLixeira = ({ className }: P) => (
  <Svg className={className}>
    <path d="M4 7h16" />
    <path d="M9 7V4h6v3" />
    <path d="M6 7l1 13h10l1-13" />
  </Svg>
);

export const IconeSeta = ({ className }: P) => (
  <Svg className={className}>
    <path d="M9 5l7 7-7 7" />
  </Svg>
);

/** Duas setas opostas: trocar de papel. */
export const IconeTrocar = ({ className }: P) => (
  <Svg className={className}>
    <path d="M4 8h14l-3-3" />
    <path d="M20 16H6l3 3" />
  </Svg>
);

export const IconeCasa = ({ className }: P) => (
  <Svg className={className}>
    <path d="M4 10.5L12 4l8 6.5V20h-5v-6H9v6H4z" />
  </Svg>
);

export const IconeGrafico = ({ className }: P) => (
  <Svg className={className}>
    <path d="M4 4v16h16" />
    <path d="M7 15l4-4 3 3 5-6" />
  </Svg>
);

export const IconePessoa = ({ className }: P) => (
  <Svg className={className}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
  </Svg>
);

export const IconeEnvelope = ({ className }: P) => (
  <Svg className={className}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M3.5 6.5L12 13l8.5-6.5" />
  </Svg>
);

export const IconeEngrenagem = ({ className }: P) => (
  <Svg className={className}>
    <path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1" />
    <circle cx="15" cy="6" r="2" />
    <circle cx="9" cy="12" r="2" />
    <circle cx="17" cy="18" r="2" />
  </Svg>
);

/** Balão de conversa: consulta por escrito com o paciente da IA. */
export const IconeBalao = ({ className }: P) => (
  <Svg className={className}>
    <path d="M5 5h14a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-8l-4 3.5V16H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z" />
    <path d="M8 9.5h8M8 12.5h5" />
  </Svg>
);

/** Seta para cima: enviar a pergunta. */
export const IconeEnviar = ({ className }: P) => (
  <Svg className={className}>
    <path d="M12 19V5M6 11l6-6 6 6" />
  </Svg>
);

export const IconeSom = ({ className }: P) => (
  <Svg className={className}>
    <path d="M4 9v6h4l5 4V5L8 9H4z" />
    <path d="M16.5 8.5a5 5 0 0 1 0 7" />
    <path d="M19 6a8.5 8.5 0 0 1 0 12" />
  </Svg>
);

export const IconeSemSom = ({ className }: P) => (
  <Svg className={className}>
    <path d="M4 9v6h4l5 4V5L8 9H4z" />
    <path d="M17 10l4 4M21 10l-4 4" />
  </Svg>
);
