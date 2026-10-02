import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { marcarDirecao, movimentoReduzido } from "../util/movimento";
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
  /** Algo no canto direito do topo, antes do selo de demonstração (avatar do perfil). */
  canto?: ReactNode;
  /** Classe extra na moldura, para telas com layout próprio (gravar). */
  className?: string;
  /** Muda a chave para o título entrar de novo, quando ele troca (gravar → gravando). */
  chaveTitulo?: string;
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
  canto,
  className,
  chaveTitulo,
  children,
  rodape,
}: Props) {
  return (
    <div className={className ? `app-tela ${className}` : "app-tela"}>
      <header className="app-topo">
        <div className="app-topo-linha">
          {voltar ? (
            <Link
              className="app-voltar"
              to={voltar}
              aria-label={rotuloVoltar}
              viewTransition={!movimentoReduzido()}
              onClick={() => marcarDirecao("voltar")}
            >
              <IconeVoltar />
            </Link>
          ) : (
            <span />
          )}
          <span className="app-topo-canto">
            <SeloDemonstracao />
            {canto}
          </span>
        </div>
        {sobretitulo && <p className="app-sobretitulo">{sobretitulo}</p>}
        <h1 className="app-titulo" key={chaveTitulo}>
          {titulo}
        </h1>
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
      <span className="app-brilho">{texto}</span>
    </p>
  );
}
