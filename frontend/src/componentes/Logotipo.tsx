import { useTema } from "../util/tema";

/** Símbolo + nome (componente Logotipo da marca). O símbolo troca com o tema. */
export function Logotipo({ tamanho = 44 }: { tamanho?: number }) {
  const tema = useTema();
  const arquivo = tema === "escuro" ? "/simbolo-escuro.svg" : "/simbolo-claro.svg";
  return (
    <span className="al-logo">
      <img src={arquivo} width={tamanho} height={tamanho} alt="" />
      <span className="al-logo-nome">
        Anamne<b>Lab</b>
      </span>
    </span>
  );
}
