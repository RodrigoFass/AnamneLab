import { NavLink, useLocation } from "react-router-dom";
import { marcarDirecao, movimentoReduzido, vibrar } from "../util/movimento";
import { IconeCasa, IconeGrafico, IconePessoa } from "./Icones";

const ABAS = [
  { para: "/", rotulo: "Início", icone: <IconeCasa /> },
  { para: "/evolucao", rotulo: "Evolução", icone: <IconeGrafico /> },
  { para: "/perfil", rotulo: "Perfil", icone: <IconePessoa /> },
];

/** Barra de abas do rodapé. O fundo da aba ativa desliza até ela (mola, sem quique). */
export function Abas() {
  const { pathname } = useLocation();
  const ativa = Math.max(
    0,
    ABAS.findIndex((a) => a.para === pathname),
  );
  return (
    <nav className="app-abas" aria-label="Seções">
      <div className="app-abas-trilho" style={{ ["--aba" as string]: ativa }}>
        <span className="app-abas-marca" aria-hidden="true" />
        {ABAS.map((a) => (
          <NavLink
            key={a.para}
            to={a.para}
            end
            viewTransition={!movimentoReduzido()}
            className="app-aba"
            onClick={() => {
              marcarDirecao("aba");
              vibrar(8);
            }}
          >
            {a.icone}
            <span>{a.rotulo}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
