import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, textoDoErro } from "../api/cliente";
import type { SessaoResumo, StatusSessao } from "../api/tipos";
import { useAuth } from "../auth/Autenticacao";
import { Aviso } from "../componentes/Aviso";
import { IconeArco, IconeAviso, IconeCheck } from "../componentes/Icones";
import { Logotipo } from "../componentes/Logotipo";
import { formatarData } from "../util/formato";
import { nomesDasQueixas, useQueixas } from "../util/sessao";

function StatusResumo({ status }: { status: StatusSessao }) {
  if (status === "concluida") {
    return (
      <span className="app-status app-status-ok">
        <IconeCheck />
        Concluída
      </span>
    );
  }
  if (status === "erro") {
    return (
      <span className="app-status app-status-erro">
        <IconeAviso />
        Não terminou
      </span>
    );
  }
  return (
    <span className="app-status">
      <IconeArco />
      Em andamento
    </span>
  );
}

function textoNota(n: number | null | undefined): string {
  return n === null || n === undefined ? "sem nota" : String(n);
}

export function Inicio() {
  const navegar = useNavigate();
  const { loginAtivo, email, sair } = useAuth();
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

  return (
    <div className="app-tela app-inicio">
      <header className="app-inicio-topo">
        <Logotipo />
        <p className="app-assinatura">Pergunte melhor.</p>
        <p className="app-descritor">Treino de anamnese com correção na hora.</p>
      </header>

      <main className="app-conteudo">
        <button
          className="al-botao al-botao-principal app-botao-largo"
          type="button"
          onClick={() => navegar("/sessao/nova")}
        >
          Começar sessão
        </button>

        <section className="app-secao" aria-labelledby="titulo-historico">
          <h2 className="app-subtitulo" id="titulo-historico">
            Suas sessões
          </h2>
          {erro && <Aviso tipo="erro">{erro}</Aviso>}
          {!erro && sessoes === null && <p className="app-carregando">Carregando o histórico…</p>}
          {sessoes?.length === 0 && (
            <p className="app-vazio">
              Nenhuma sessão ainda. Chame um colega, escolha um caso e grave a primeira.
            </p>
          )}
          {sessoes && sessoes.length > 0 && (
            <ul className="app-historico">
              {sessoes.map((s) => (
                <li key={s.id}>
                  <Link className="app-historico-item" to={`/sessao/${s.id}`}>
                    <span className="app-historico-queixa">
                      {s.queixas_confirmadas.length > 0
                        ? nomesDasQueixas(s.queixas_confirmadas, queixas)
                        : "Queixa a confirmar"}
                    </span>
                    <span className="app-historico-data">{formatarData(s.criada_em)}</span>
                    <span className="app-historico-linha">
                      <StatusResumo status={s.status} />
                      {s.notas && (
                        <span className="app-historico-notas app-tabular">
                          Geral {textoNota(s.notas.geral)} · Queixa {textoNota(s.notas.queixa)}
                          {s.notas.provisoria ? " · provisória" : ""}
                        </span>
                      )}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        {loginAtivo && (
          <p className="app-conta">
            {email ? `Conectado como ${email}. ` : ""}
            <button className="al-botao al-botao-texto" type="button" onClick={() => void sair()}>
              Sair
            </button>
          </p>
        )}
      </main>
    </div>
  );
}
