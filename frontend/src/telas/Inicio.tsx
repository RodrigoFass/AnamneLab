import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, textoDoErro } from "../api/cliente";
import type { SessaoResumo } from "../api/tipos";
import { Aviso } from "../componentes/Aviso";
import { Avatar } from "../componentes/Avatar";
import { SeloDemonstracao } from "../componentes/AvisoDemonstracao";
import { Contador } from "../componentes/Contador";
import { LinhaNotas } from "../componentes/Grafico";
import { IconeArco, IconeAviso, IconeMicrofone, IconeSeta } from "../componentes/Icones";
import { Logotipo } from "../componentes/Logotipo";
import { formatarRelativo } from "../util/formato";
import { marcarDirecao, movimentoReduzido, useNavegar } from "../util/movimento";
import { linhaDoPerfil, primeiroNome, usePerfil } from "../util/perfil";
import { nomesDasQueixas, useQueixas } from "../util/sessao";

function Situacao({ s }: { s: SessaoResumo }) {
  if (s.status === "concluida" || s.notas) return <>{formatarRelativo(s.criada_em)}</>;
  if (s.status === "erro") {
    return (
      <span className="app-status app-status-erro">
        <IconeAviso />
        Não terminou · {formatarRelativo(s.criada_em)}
      </span>
    );
  }
  return (
    <span className="app-status">
      <IconeArco />
      Em andamento · {formatarRelativo(s.criada_em)}
    </span>
  );
}

function UltimaSessao({ sessoes, nome }: { sessoes: SessaoResumo[]; nome: string }) {
  // A lista chega da mais nova para a mais antiga; o gráfico vai da antiga para a nova.
  const comNota = sessoes.filter((s) => typeof s.notas?.geral === "number");
  const ultima = comNota[0];
  if (!ultima) return null;
  const linha = comNota
    .slice(0, 6)
    .map((s) => s.notas?.geral as number)
    .reverse();
  return (
    <Link
      className="app-ultima"
      to={`/sessao/${ultima.id}`}
      viewTransition={!movimentoReduzido()}
      onClick={() => marcarDirecao("avancar")}
    >
      <div>
        <p className="app-legenda">Última sessão</p>
        <p className="app-ultima-nota app-tabular">
          <Contador texto={String(ultima.notas?.geral)} doZero />
        </p>
        <p className="app-legenda">
          {nome} · {formatarRelativo(ultima.criada_em)}
        </p>
      </div>
      <LinhaNotas notas={linha} />
    </Link>
  );
}

export function Inicio() {
  const navegar = useNavegar();
  const perfil = usePerfil();
  const { queixas } = useQueixas();
  const [sessoes, setSessoes] = useState<SessaoResumo[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;
    api.sessoes().then(
      (s) => ativo && setSessoes(s),
      (e: unknown) => ativo && setErro(textoDoErro(e)),
    );
    return () => {
      ativo = false;
    };
  }, []);

  const nomeDa = (s: SessaoResumo) =>
    s.queixas_confirmadas.length > 0 ? nomesDasQueixas(s.queixas_confirmadas, queixas) : "Queixa a confirmar";

  const ultimaComNota = sessoes?.find((s) => typeof s.notas?.geral === "number");

  return (
    <div className="app-tela app-inicio app-tela-abas">
      <header className="app-inicio-topo">
        <div className="app-topo-linha">
          <Logotipo tamanho={28} />
          <span className="app-topo-canto">
            <SeloDemonstracao />
            <Link
              to="/perfil"
              aria-label="Perfil"
              viewTransition={!movimentoReduzido()}
              onClick={() => marcarDirecao("aba")}
            >
              <Avatar nome={perfil.nome} papel="medico" tamanho={32} />
            </Link>
          </span>
        </div>
        <h1 className="app-assinatura">Olá, {primeiroNome(perfil.nome)}</h1>
        <p className="app-descritor">{linhaDoPerfil(perfil) || "Pergunte melhor."}</p>
      </header>

      <main className="app-conteudo">
        {sessoes && ultimaComNota && <UltimaSessao sessoes={sessoes} nome={nomeDa(ultimaComNota)} />}

        <button
          className="al-botao al-botao-principal app-botao-largo"
          type="button"
          onClick={() => navegar("/sessao/nova")}
        >
          <IconeMicrofone />
          Começar sessão
        </button>

        <section className="app-secao" aria-labelledby="titulo-historico">
          <h2 className="app-subtitulo" id="titulo-historico">
            Seu histórico
          </h2>
          {erro && <Aviso tipo="erro">{erro}</Aviso>}
          {!erro && sessoes === null && <p className="app-carregando">Carregando o histórico…</p>}
          {sessoes?.length === 0 && (
            <p className="app-vazio">
              Nenhuma sessão ainda. Chame um colega, escolha um caso e grave a primeira.
            </p>
          )}
          {sessoes && sessoes.length > 0 && (
            <ul className="app-lista app-cascata">
              {sessoes.map((s) => (
                <li key={s.id}>
                  <Link
                    className="app-lista-linha"
                    to={`/sessao/${s.id}`}
                    viewTransition={!movimentoReduzido()}
                    onClick={() => marcarDirecao("avancar")}
                  >
                    <span className="app-lista-texto">
                      <span className="app-lista-titulo">{nomeDa(s)}</span>
                      <span className="app-lista-meta">
                        <Situacao s={s} />
                      </span>
                    </span>
                    {typeof s.notas?.geral === "number" && (
                      <span className="app-lista-nota app-tabular" aria-label={`Técnica geral ${s.notas.geral}`}>
                        {s.notas.geral}
                      </span>
                    )}
                    <IconeSeta className="app-lista-seta" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

      </main>
    </div>
  );
}
