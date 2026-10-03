import { useCallback, useEffect, useState } from "react";
import { api, textoDoErro } from "../api/cliente";
import type { ContaPainel, Painel as TipoPainel, SessaoPainel, StatusSessao } from "../api/tipos";
import { Aviso } from "../componentes/Aviso";
import { Avatar } from "../componentes/Avatar";
import { Contador } from "../componentes/Contador";
import { IconeArco, IconeAviso, IconeBalao, IconeCheck, IconeMicrofone } from "../componentes/Icones";
import { Carregando, Tela } from "../componentes/Tela";
import { formatarData, formatarRelativo } from "../util/formato";
import { nomesDasQueixas, useQueixas } from "../util/sessao";

const STATUS: Record<StatusSessao, string> = {
  criada: "Abriu e não gravou",
  conversando: "Conversando",
  processando_audio: "Transcrevendo",
  aguardando_queixa: "Parou na queixa",
  corrigindo: "Corrigindo",
  aguardando_hipoteses: "Parou nas hipóteses",
  gerando_sugestoes: "Corrigindo",
  concluida: "Concluída",
  erro: "Não terminou",
};

function nomeDaConta(c: ContaPainel | undefined): string {
  if (!c) return "Conta apagada";
  return c.nome || c.email || "Sem nome";
}

/** "Rodrigo" ou, sem nome, a parte do e-mail antes do @. */
function apelido(c: ContaPainel | undefined): string {
  if (!c) return "Conta apagada";
  return c.nome?.split(" ")[0] || c.email?.split("@")[0] || "Sem nome";
}

function ultimaAtividade(c: ContaPainel): string | null {
  const datas = [c.ultima_sessao, c.ultimo_login].filter((d): d is string => Boolean(d));
  return datas.length ? datas.sort().at(-1)! : null;
}

function Situacao({ status }: { status: StatusSessao }) {
  if (status === "concluida") {
    return (
      <span className="app-status app-status-ok">
        <IconeCheck />
        {STATUS[status]}
      </span>
    );
  }
  if (status === "erro") {
    return (
      <span className="app-status app-status-erro">
        <IconeAviso />
        {STATUS[status]}
      </span>
    );
  }
  return (
    <span className="app-status">
      <IconeArco />
      {STATUS[status]}
    </span>
  );
}

function Barras({ dias }: { dias: TipoPainel["por_dia"] }) {
  const max = Math.max(1, ...dias.map((d) => d.sessoes));
  const total = dias.reduce((a, d) => a + d.sessoes, 0);
  const curta = (iso: string) => {
    const [, mes, dia] = iso.split("-");
    return `${dia}/${mes}`;
  };
  return (
    <figure className="app-painel-barras">
      <div
        className="app-painel-barras-area"
        role="img"
        aria-label={`Sessões por dia nos últimos 14 dias, ${total} no total: ${dias.map((d) => `${curta(d.dia)} ${d.sessoes}`).join(", ")}`}
      >
        {dias.map((d) => (
          <div key={d.dia} className="app-painel-barra" title={`${curta(d.dia)}: ${d.sessoes} sessões`}>
            {d.sessoes > 0 && <span className="app-painel-barra-valor app-tabular">{d.sessoes}</span>}
            <span className="app-painel-barra-cheia" style={{ height: `${(d.sessoes / max) * 100}%` }} />
          </div>
        ))}
      </div>
      <figcaption className="app-painel-barras-eixo app-legenda">
        <span>{curta(dias[0]?.dia ?? "")}</span>
        <span>hoje</span>
      </figcaption>
    </figure>
  );
}

function Pessoa({ c }: { c: ContaPainel }) {
  const ultima = ultimaAtividade(c);
  const detalhe = [c.email && c.nome ? c.email : null, c.faculdade, c.periodo ? `${c.periodo} período` : null]
    .filter(Boolean)
    .join(" · ");
  return (
    <li className="app-painel-pessoa">
      <Avatar nome={c.nome || c.email || "?"} papel="medico" tamanho={44} avatar={c.avatar ?? ""} />
      <div className="app-painel-pessoa-texto">
        <p className="app-lista-titulo">{nomeDaConta(c)}</p>
        {detalhe && <p className="app-lista-meta">{detalhe}</p>}
        <p className="app-painel-pessoa-numeros">
          {c.sessoes === 0 ? (
            "Ainda não abriu nenhuma sessão"
          ) : (
            <>
              <span>
                <IconeMicrofone /> {c.com_colega} com colega
              </span>
              <span>
                <IconeBalao /> {c.paciente_ia} com o paciente da IA
              </span>
              <span>
                <IconeCheck /> {c.concluidas} {c.concluidas === 1 ? "concluída" : "concluídas"}
              </span>
            </>
          )}
        </p>
        <p className="app-lista-meta">
          {ultima ? `Mexeu ${formatarRelativo(ultima)}` : "Sem atividade"}
          {c.criada_em ? ` · conta criada em ${formatarData(c.criada_em)}` : ""}
        </p>
      </div>
      {c.media_geral !== null && (
        <span className="app-painel-pessoa-media" aria-label={`Média de técnica geral ${c.media_geral}`}>
          <span className="app-lista-nota app-tabular">{c.media_geral}</span>
          <span className="app-lista-meta">média</span>
        </span>
      )}
    </li>
  );
}

export function Painel() {
  const [painel, setPainel] = useState<TipoPainel | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [atualizando, setAtualizando] = useState(false);
  const { queixas } = useQueixas();

  const carregar = useCallback(() => {
    setAtualizando(true);
    setErro(null);
    api
      .painel()
      .then(setPainel, (e: unknown) => setErro(textoDoErro(e)))
      .finally(() => setAtualizando(false));
  }, []);

  useEffect(carregar, [carregar]);

  const contas = new Map((painel?.contas ?? []).map((c) => [c.id, c]));
  const r = painel?.resumo;

  return (
    <Tela
      titulo="Painel"
      subtitulo={painel ? `O que as pessoas estão fazendo no app · atualizado ${formatarData(painel.gerado_em)}` : "O que as pessoas estão fazendo no app"}
      voltar="/perfil"
    >
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      {!painel && !erro && <Carregando />}
      {painel && r && (
        <>
          {!painel.contas_completas && (
            <Aviso>Sem login ligado, o painel mostra só quem já abriu alguma sessão neste computador.</Aviso>
          )}

          <dl className="app-numeros app-cascata">
            <div>
              <dt>Contas</dt>
              <dd>
                <Contador texto={String(r.contas)} doZero />
              </dd>
            </div>
            <div>
              <dt>Ativas na semana</dt>
              <dd>
                <Contador texto={String(r.ativas_7_dias)} doZero />
              </dd>
            </div>
            <div>
              <dt>Sessões na semana</dt>
              <dd>
                <Contador texto={String(r.sessoes_7_dias)} doZero />
              </dd>
            </div>
            <div>
              <dt>Sessões no total</dt>
              <dd>
                <Contador texto={String(r.sessoes)} doZero />
              </dd>
            </div>
            <div>
              <dt>Com o paciente da IA</dt>
              <dd>
                <Contador texto={String(r.paciente_ia)} doZero />
              </dd>
            </div>
            <div>
              <dt>Concluídas</dt>
              <dd>
                <Contador texto={String(r.concluidas)} doZero />
              </dd>
            </div>
          </dl>

          <section className="app-secao" aria-labelledby="titulo-dias">
            <h2 className="app-subtitulo" id="titulo-dias">
              Sessões por dia
            </h2>
            <Barras dias={painel.por_dia} />
          </section>

          <section className="app-secao" aria-labelledby="titulo-pessoas">
            <h2 className="app-subtitulo" id="titulo-pessoas">
              Pessoas
            </h2>
            {painel.contas.length === 0 ? (
              <p className="app-vazio">Ninguém criou conta ainda.</p>
            ) : (
              <ul className="app-painel-pessoas app-cascata">
                {painel.contas.map((c) => (
                  <Pessoa key={c.id} c={c} />
                ))}
              </ul>
            )}
          </section>

          <section className="app-secao" aria-labelledby="titulo-recentes">
            <h2 className="app-subtitulo" id="titulo-recentes">
              Últimas sessões
            </h2>
            {painel.recentes.length === 0 ? (
              <p className="app-vazio">Nenhuma sessão ainda.</p>
            ) : (
              <ul className="app-lista">
                {painel.recentes.map((s: SessaoPainel) => {
                  const queixa = s.queixas_confirmadas.length
                    ? nomesDasQueixas(s.queixas_confirmadas, queixas, s.descricao_outra)
                    : null;
                  return (
                    <li key={s.id}>
                      <div className="app-lista-linha">
                        <span className="app-lista-texto">
                          <span className="app-lista-titulo">
                            {apelido(contas.get(s.conta_id))} ·{" "}
                            {s.origem_caso === "paciente_ia" ? "paciente da IA" : "com colega"}
                          </span>
                          <span className="app-lista-meta">
                            {queixa ? `${queixa} · ` : ""}
                            {formatarRelativo(s.criada_em)} · <Situacao status={s.status} />
                          </span>
                        </span>
                        {s.nota_geral !== null && (
                          <span className="app-lista-nota app-tabular" aria-label={`Técnica geral ${s.nota_geral}`}>
                            {s.nota_geral}
                          </span>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          {painel.queixas.length > 0 && (
            <section className="app-secao" aria-labelledby="titulo-queixas">
              <h2 className="app-subtitulo" id="titulo-queixas">
                Queixas mais treinadas
              </h2>
              <ul className="app-lista">
                {painel.queixas.map((q) => (
                  <li key={q.queixa}>
                    <div className="app-lista-linha">
                      <span className="app-lista-texto">
                        <span className="app-lista-titulo">{nomesDasQueixas([q.queixa], queixas)}</span>
                      </span>
                      <span className="app-lista-nota app-tabular">{q.vezes}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <p className="app-legenda">
            O painel mostra números, datas, queixas e notas. Transcrições e correções continuam só com cada aluno.
          </p>
        </>
      )}
      <button className="al-botao al-botao-secundario app-botao-largo" type="button" disabled={atualizando} onClick={carregar}>
        {atualizando ? "Atualizando…" : "Atualizar"}
      </button>
    </Tela>
  );
}
