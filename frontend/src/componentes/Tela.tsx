import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { SeloDemonstracao } from "./AvisoDemonstracao";
import { IconeVoltar } from "./Icones";

interface Props {
  titulo: string;
  /** Linha pequena acima do título ("Ana e Pedro · cartão sorteado"). */
  sobretitulo?: string;
  /** Linha pequena abaixo do título ("Leva de um a três minutos."). */
  subtitulo?: string;
  /** Rota do botão de voltar; sem ela, o topo não mostra voltar. */
  voltar?: string;
  rotuloVoltar?: string;
  /** Classe extra na moldura, para telas com layout próprio (gravar). */
  className?: string;
  children: ReactNode;
  rodape?: ReactNode;
}

/** Moldura de cada tela: topo com voltar, título e conteúdo em coluna. */
export function Tela({
  titulo,
  sobretitulo,
  subtitulo,
  voltar,
  rotuloVoltar = "Voltar",
  className,
  children,
  rodape,
}: Props) {
  return (
    <div className={className ? `app-tela ${className}` : "app-tela"}>
      <header className="app-topo">
        <div className="app-topo-linha">
          {voltar ? (
            <Link className="app-voltar" to={voltar} aria-label={rotuloVoltar}>
              <IconeVoltar />
            </Link>
          ) : (
            <span />
          )}
          <SeloDemonstracao />
        </div>
        {sobretitulo && <p className="app-sobretitulo">{sobretitulo}</p>}
        <h1 className="app-titulo">{titulo}</h1>
        {subtitulo && <p className="app-subtitulo-tela">{subtitulo}</p>}
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
