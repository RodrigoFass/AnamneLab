import { useEffect, useState } from "react";
import { movimentoReduzido } from "../util/movimento";

const ALGARISMOS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"];

interface Props {
  /** Texto com algarismos ("82", "05:41"); o que não é algarismo fica parado. */
  texto: string;
  /** Rótulo para leitor de tela; sem ele, lê o próprio texto. */
  rotulo?: string;
  /** Rola a partir do zero ao aparecer (nota); sem isso, só rola quando muda (cronômetro). */
  doZero?: boolean;
  className?: string;
}

/**
 * Número que rola algarismo por algarismo, como um contador de placar. Cada algarismo
 * é uma coluna de 0 a 9 que desliza na vertical (só transform). Com movimento reduzido, troca direto.
 */
export function Contador({ texto, rotulo, doZero = false, className }: Props) {
  const [mostrado, setMostrado] = useState(() =>
    doZero && !movimentoReduzido() ? texto.replace(/\d/g, "0") : texto,
  );

  useEffect(() => {
    // Um quadro depois de montar, para a coluna sair do zero com transição.
    const q = requestAnimationFrame(() => setMostrado(texto));
    return () => cancelAnimationFrame(q);
  }, [texto]);

  const casas = mostrado.split("");
  return (
    <span className={className ? `app-tic ${className}` : "app-tic"}>
      <span className="app-so-leitor">{rotulo ?? texto}</span>
      {casas.map((c, i) => {
        if (!/\d/.test(c)) {
          return (
            <span key={i} className="app-tic-fixo" aria-hidden="true">
              {c}
            </span>
          );
        }
        // Algarismos da esquerda chegam um pouco depois, como num odômetro.
        const atraso = (casas.length - 1 - i) * 70;
        return (
          <span key={i} className="app-tic-casa" aria-hidden="true">
            <span
              className="app-tic-coluna"
              style={{ transform: `translateY(${-Number(c) * 10}%)`, transitionDelay: `${atraso}ms` }}
            >
              {ALGARISMOS.map((a) => (
                <span key={a}>{a}</span>
              ))}
            </span>
          </span>
        );
      })}
    </span>
  );
}
