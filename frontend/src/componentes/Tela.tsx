import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { IconeVoltar } from "./Icones";

interface Props {
  titulo: string;
  /** Rota do botão de voltar; sem ela, o topo não mostra voltar. */
  voltar?: string;
  rotuloVoltar?: string;
  children: ReactNode;
  rodape?: ReactNode;
}

/** Moldura de cada tela: topo com voltar, título e conteúdo em coluna. */
export function Tela({ titulo, voltar, rotuloVoltar = "Voltar", children, rodape }: Props) {
  return (
    <div className="app-tela">
      <header className="app-topo">
        {voltar && (
          <Link className="app-voltar" to={voltar} aria-label={rotuloVoltar}>
            <IconeVoltar />
          </Link>
        )}
        <h1 className="app-titulo">{titulo}</h1>
      </header>
      <main className="app-conteudo">{children}</main>
      {rodape && <footer className="app-rodape">{rodape}</footer>}
    </div>
  );
}

export function Carregando({ texto = "Carregando…" }: { texto?: string }) {
  return (
    <p className="app-carregando" role="status">
      {texto}
    </p>
  );
}
