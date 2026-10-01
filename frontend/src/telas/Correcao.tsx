import { useId, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { api, textoDoErro } from "../api/cliente";
import type {
  AnamneseEstruturada,
  Avaliacao,
  ChecklistUsado,
  Contestacao,
  Fala,
  Queixa,
  Sessao,
} from "../api/tipos";
import { Aviso } from "../componentes/Aviso";
import { BarraProgresso } from "../componentes/BarraProgresso";
import { IconeArco, IconeAviso, IconeCheck } from "../componentes/Icones";
import { ItemChecklist, ItemSugestao } from "../componentes/ItemChecklist";
import { NotaSessao } from "../componentes/NotaSessao";
import { Selo } from "../componentes/Selo";
import { Carregando, Tela } from "../componentes/Tela";
import { humanizar, normalizar } from "../util/formato";
import { nomesDasQueixas, rotaDaSessao, useQueixas, useSessao } from "../util/sessao";

const ID_GERAL = "geral";

const CAMPOS_ANAMNESE: { campo: keyof AnamneseEstruturada; rotulo: string }[] = [
  { campo: "identificacao", rotulo: "Identificação" },
  { campo: "queixa_principal", rotulo: "Queixa principal" },
  { campo: "hda", rotulo: "História da doença atual (HDA)" },
  { campo: "interrogatorio_sintomatologico", rotulo: "Interrogatório sintomatológico" },
  { campo: "antecedentes_pessoais", rotulo: "Antecedentes pessoais" },
  { campo: "antecedentes_familiares", rotulo: "Antecedentes familiares" },
  { campo: "habitos_de_vida", rotulo: "Hábitos de vida" },
  { campo: "condicoes_socioeconomicas", rotulo: "Condições socioeconômicas" },
];

function nomeDoChecklist(id: string, queixas: Queixa[]): string {
  if (id === ID_GERAL) return "Técnica geral";
  return queixas.find((q) => q.checklist === id)?.nome ?? humanizar(id);
}

/** Quem disse o trecho citado, procurando nas falas da transcrição. */
function quemFalou(trecho: string | null, falas: Fala[]): string {
  if (!trecho) return "Trecho da conversa";
  const alvo = normalizar(trecho);
  const fala = falas.find((f) => normalizar(f.texto).includes(alvo));
  if (!fala) return "Trecho da conversa";
  return fala.papel === "entrevistador" ? "Você disse" : "O paciente disse";
}

interface SecaoItens {
  secao: string;
  itens: Avaliacao[];
}

interface Grupo {
  checklistId: string;
  usado: ChecklistUsado | undefined;
  /** Faltou (e item contestado, para o aluno ver o resultado): sempre aberto. */
  abertos: SecaoItens[];
  /** Feito: recolhido atrás de um botão. */
  feitos: SecaoItens[];
  totalFeitos: number;
}

/** Agrupa por seção mantendo a ordem do checklist. */
function porSecao(avaliacoes: Avaliacao[]): SecaoItens[] {
  const secoes: SecaoItens[] = [];
  for (const a of avaliacoes) {
    let s = secoes.find((x) => x.secao === a.secao);
    if (!s) {
      s = { secao: a.secao, itens: [] };
      secoes.push(s);
    }
    s.itens.push(a);
  }
  return secoes;
}

function agrupar(sessao: Sessao): Grupo[] {
  const ordem = sessao.checklists_usados.map((c) => c.id);
  for (const a of sessao.avaliacoes) if (!ordem.includes(a.checklist_id)) ordem.push(a.checklist_id);

  return ordem
    .map((checklistId) => {
      const doChecklist = sessao.avaliacoes.filter((x) => x.checklist_id === checklistId);
      // Item contestado fica à vista mesmo quando virou feito: o aluno vê o resultado na hora.
      const aberto = (a: Avaliacao) => a.status === "faltou" || Boolean(a.contestacao);
      const feitos = doChecklist.filter((a) => !aberto(a));
      return {
        checklistId,
        usado: sessao.checklists_usados.find((c) => c.id === checklistId),
        abertos: porSecao(doChecklist.filter(aberto)),
        feitos: porSecao(feitos),
        totalFeitos: feitos.length,
      };
    })
    .filter((g) => g.abertos.length > 0 || g.feitos.length > 0);
}

function contagem(avaliacoes: Avaliacao[]): string {
  const valem = avaliacoes.filter((a) => a.conta_na_nota);
  const faltaram = valem.filter((a) => a.status === "faltou").length;
  if (valem.length === 0) return "";
  const total = valem.length === 1 ? "1 item" : `${valem.length} itens`;
  if (faltaram === 0) return `Você fez ${valem.length === 1 ? "o item" : `todos os ${total}`}.`;
  return `${faltaram === 1 ? "Faltou 1" : `Faltaram ${faltaram}`} de ${total}.`;
}

function ResultadoContestacao({ c }: { c: Contestacao }) {
  if (c.resultado === "procedente") {
    return (
      <p className="app-status app-status-ok app-contestacao-resultado">
        <IconeCheck />
        Contestação aceita: o trecho mostra que você investigou o item. Ele contou como feito e a
        nota foi recalculada.
      </p>
    );
  }
  return (
    <p className="app-status app-contestacao-resultado">
      <IconeAviso />
      Contestação enviada para o professor revisar. A nota não muda até lá.
    </p>
  );
}

interface PropsContestar {
  sessao: Sessao;
  item: Avaliacao;
  onFechar: () => void;
  onAtualizada: (s: Sessao) => void;
}

function FormContestar({ sessao, item, onFechar, onAtualizada }: PropsContestar) {
  const [motivo, setMotivo] = useState("");
  const [indiceFala, setIndiceFala] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const enviar = async () => {
    setEnviando(true);
    setErro(null);
    const fala = indiceFala === "" ? undefined : sessao.falas[Number(indiceFala)];
    try {
      const nova = await api.contestar(sessao.id, {
        item_id: item.item_id,
        motivo: motivo.trim(),
        trecho: fala?.texto ?? null,
      });
      onAtualizada(nova);
      onFechar();
    } catch (e) {
      setErro(textoDoErro(e));
      setEnviando(false);
    }
  };

  const idBase = `contestar-${item.checklist_id}-${item.item_id}`;
  return (
    <form
      className="app-contestar-form"
      onSubmit={(e) => {
        e.preventDefault();
        void enviar();
      }}
    >
      <label className="app-campo" htmlFor={`${idBase}-motivo`}>
        <span className="app-campo-rotulo">Por que você discorda?</span>
        <textarea
          id={`${idBase}-motivo`}
          rows={3}
          maxLength={1000}
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          required
        />
      </label>
      <label className="app-campo" htmlFor={`${idBase}-trecho`}>
        <span className="app-campo-rotulo">Fala que prova (opcional)</span>
        <select id={`${idBase}-trecho`} value={indiceFala} onChange={(e) => setIndiceFala(e.target.value)}>
          <option value="">Sem trecho: mandar para o professor</option>
          {sessao.falas.map((f, i) => (
            <option key={i} value={String(i)}>
              {f.papel === "entrevistador" ? "Você: " : "Paciente: "}
              {f.texto.length > 90 ? `${f.texto.slice(0, 90)}…` : f.texto}
            </option>
          ))}
        </select>
      </label>
      <p className="app-legenda">
        Se a fala mostrar que você investigou o item, ele conta como feito na hora. Sem fala, ou
        se a fala não mostrar o item, a contestação vai para o professor e a nota não muda.
      </p>
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <div className="app-acoes">
        <button className="al-botao al-botao-secundario" type="submit" disabled={!motivo.trim() || enviando}>
          {enviando ? "Enviando…" : "Enviar contestação"}
        </button>
        <button className="al-botao al-botao-texto" type="button" onClick={onFechar} disabled={enviando}>
          Cancelar
        </button>
      </div>
    </form>
  );
}

interface PropsChecklist {
  grupo: Grupo;
  sessao: Sessao;
  queixas: Queixa[];
  contestando: string | null;
  onContestando: (chave: string | null) => void;
  onAtualizada: (s: Sessao) => void;
}

/** Um checklist corrigido: o que faltou aberto, o que foi feito recolhido. */
function ChecklistCorrigido({ grupo, sessao, queixas, contestando, onContestando, onAtualizada }: PropsChecklist) {
  const [verFeitos, setVerFeitos] = useState(false);
  const idFeitos = useId();
  const g = grupo;

  const itens = (secoes: SecaoItens[]) =>
    secoes.map((s) => (
      <div key={s.secao} className="app-secao-itens">
        <h3 className="app-secao-titulo">{humanizar(s.secao)}</h3>
        {s.itens.map((a) => {
          const chave = `${a.checklist_id}:${a.item_id}`;
          const aberto = contestando === chave;
          return (
            <ItemChecklist
              key={chave}
              avaliacao={a}
              quemFalou={quemFalou(a.trecho, sessao.falas)}
              onContestar={() => onContestando(aberto ? null : chave)}
              contestando={aberto}
            >
              {a.contestacao && <ResultadoContestacao c={a.contestacao} />}
              {aberto && !a.contestacao && (
                <FormContestar
                  sessao={sessao}
                  item={a}
                  onFechar={() => onContestando(null)}
                  onAtualizada={onAtualizada}
                />
              )}
            </ItemChecklist>
          );
        })}
      </div>
    ));

  const rotuloFeitos =
    g.totalFeitos === 1 ? "Ver o item feito" : `Ver os ${g.totalFeitos} itens feitos`;

  return (
    <section className="app-secao" aria-labelledby={`chk-${g.checklistId}`}>
      <div className="app-checklist-topo">
        <h2 className="app-subtitulo" id={`chk-${g.checklistId}`}>
          {nomeDoChecklist(g.checklistId, queixas)}
        </h2>
        {g.usado && <Selo checklist={g.usado} />}
      </div>
      {g.usado && <p className="app-legenda">Versão {g.usado.versao} do checklist.</p>}

      {g.abertos.length > 0 ? (
        itens(g.abertos)
      ) : (
        <p className="app-status app-status-ok">
          <IconeCheck />
          Nenhum item faltou neste checklist.
        </p>
      )}

      {g.totalFeitos > 0 && (
        <>
          <button
            className="al-botao al-botao-texto app-ver-mais"
            type="button"
            aria-expanded={verFeitos}
            aria-controls={idFeitos}
            onClick={() => setVerFeitos((v) => !v)}
          >
            {verFeitos ? "Esconder os itens feitos" : rotuloFeitos}
          </button>
          <div id={idFeitos} className="app-recolhido" hidden={!verFeitos}>
            {verFeitos && itens(g.feitos)}
          </div>
        </>
      )}
    </section>
  );
}

const SUGESTOES_VISIVEIS = 5;

/** Perguntas sugeridas pela IA, fora da nota. Mostra 5 e recolhe o resto. */
function PerguntasSugeridas({ perguntas }: { perguntas: string[] }) {
  const [verTodas, setVerTodas] = useState(false);
  const idResto = useId();
  const primeiras = perguntas.slice(0, SUGESTOES_VISIVEIS);
  const resto = perguntas.slice(SUGESTOES_VISIVEIS);

  return (
    <section className="app-secao" aria-labelledby="titulo-perguntas">
      <h2 className="app-subtitulo" id="titulo-perguntas">
        Perguntas que valem a pena
      </h2>
      <p className="app-ajuda">Sugestões para a próxima conversa. Não entram na nota.</p>
      {primeiras.map((p) => (
        <ItemSugestao key={p} titulo={p} />
      ))}
      {resto.length > 0 && (
        <>
          <div id={idResto} className="app-secao-itens" hidden={!verTodas}>
            {verTodas && resto.map((p) => <ItemSugestao key={p} titulo={p} />)}
          </div>
          <button
            className="al-botao al-botao-texto app-ver-mais"
            type="button"
            aria-expanded={verTodas}
            aria-controls={idResto}
            onClick={() => setVerTodas((v) => !v)}
          >
            {verTodas ? `Ver só as ${SUGESTOES_VISIVEIS} primeiras` : `Ver todas as ${perguntas.length} sugestões`}
          </button>
        </>
      )}
    </section>
  );
}

export function Correcao() {
  const { id } = useParams();
  const navegar = useNavigate();
  const { sessao, erro: erroSessao, definir } = useSessao(id, (s) => s.status === "gerando_sugestoes");
  const { queixas } = useQueixas();
  const [contestando, setContestando] = useState<string | null>(null);
  const [confirmarExclusao, setConfirmarExclusao] = useState(false);
  const [excluindo, setExcluindo] = useState(false);
  const [erroExclusao, setErroExclusao] = useState<string | null>(null);

  if (!id) return <Navigate to="/" replace />;
  if (sessao && rotaDaSessao(sessao) !== `/sessao/${id}/correcao`) {
    return <Navigate to={rotaDaSessao(sessao)} replace />;
  }

  const excluir = async () => {
    setExcluindo(true);
    setErroExclusao(null);
    try {
      await api.excluirSessao(id);
      navegar("/", { replace: true });
    } catch (e) {
      setErroExclusao(textoDoErro(e));
      setExcluindo(false);
    }
  };

  if (!sessao) {
    return (
      <Tela titulo="Correção" voltar="/" rotuloVoltar="Voltar ao início">
        {erroSessao ? <Aviso tipo="erro">{erroSessao}</Aviso> : <Carregando texto="Carregando a correção…" />}
      </Tela>
    );
  }

  const grupos = agrupar(sessao);
  const nomeQueixa =
    nomesDasQueixas(sessao.queixas_confirmadas, queixas, sessao.descricao_outra) || "Queixa";
  const geral = sessao.avaliacoes.filter((a) => a.checklist_id === ID_GERAL);
  const daQueixa = sessao.avaliacoes.filter((a) => a.checklist_id !== ID_GERAL);
  const temChecklistQueixa = sessao.checklists_usados.some((c) => c.id !== ID_GERAL);
  const rascunhos = sessao.checklists_usados.filter((c) => c.status === "rascunho");

  const metaQueixaSemNota = sessao.queixas_confirmadas.includes("outra")
    ? "Queixa fora da lista: a conversa foi corrigida só pela técnica geral."
    : !temChecklistQueixa
      ? "Esta queixa ainda não tem checklist. Veja as perguntas sugeridas, fora da nota."
      : "O checklist desta queixa ainda não conta na nota.";

  const sugestoes = sessao.sugestoes;
  const gerando = sessao.status === "gerando_sugestoes";

  return (
    <Tela titulo="Correção" voltar="/" rotuloVoltar="Voltar ao início">
      {erroSessao && <Aviso tipo="erro">{erroSessao}</Aviso>}
      {sessao.status === "erro" && sessao.mensagem_erro && (
        <Aviso tipo="erro">{sessao.mensagem_erro} A correção abaixo continua valendo.</Aviso>
      )}

      {sessao.notas?.provisoria && (
        <Aviso>
          Nota provisória: os critérios ainda não foram revisados por um professor.
        </Aviso>
      )}

      {sessao.notas && (
        <NotaSessao
          geral={{
            rotulo: "Técnica geral",
            nota: sessao.notas.geral,
            meta:
              sessao.notas.geral === null
                ? "O checklist geral ainda não conta na nota."
                : contagem(geral),
          }}
          queixa={{
            rotulo: nomeQueixa,
            nota: sessao.notas.queixa,
            meta: sessao.notas.queixa === null ? metaQueixaSemNota : contagem(daQueixa),
          }}
        />
      )}

      {rascunhos.length > 0 && (
        <p className="app-ajuda">
          Os checklists marcados como rascunho vieram de fontes públicas e ainda esperam a revisão
          de um professor.
        </p>
      )}

      {grupos.map((g) => (
        <ChecklistCorrigido
          key={g.checklistId}
          grupo={g}
          sessao={sessao}
          queixas={queixas}
          contestando={contestando}
          onContestando={setContestando}
          onAtualizada={definir}
        />
      ))}

      {gerando && !sugestoes && (
        <section className="app-processando">
          <p className="app-status" aria-live="polite">
            <IconeArco className="app-girando" />
            Preparando as hipóteses sugeridas e as perguntas para estudo…
          </p>
          <BarraProgresso valor={sessao.progresso} rotulo="Progresso das sugestões" />
        </section>
      )}

      {sugestoes && sugestoes.perguntas_sugeridas.length > 0 && (
        <PerguntasSugeridas perguntas={sugestoes.perguntas_sugeridas} />
      )}

      <section className="app-secao" aria-labelledby="titulo-hipoteses">
        <h2 className="app-subtitulo" id="titulo-hipoteses">
          Hipóteses
        </h2>
        <div className="app-hipoteses">
          <div className="app-hipoteses-coluna">
            <h3 className="app-secao-titulo">As suas hipóteses</h3>
            {sessao.hipoteses_aluno.length > 0 ? (
              <ol className="app-hipoteses-aluno">
                {sessao.hipoteses_aluno.map((h, i) => (
                  <li key={i}>{h}</li>
                ))}
              </ol>
            ) : (
              <p className="app-vazio">Você não escreveu hipóteses.</p>
            )}
          </div>
          <div className="app-hipoteses-coluna app-hipoteses-ia">
            <h3 className="app-secao-titulo">Hipóteses sugeridas: sugestão, não gabarito</h3>
            {!sugestoes && gerando && <p className="app-carregando">Preparando…</p>}
            {!sugestoes && !gerando && <p className="app-vazio">Sem hipóteses sugeridas nesta sessão.</p>}
            {sugestoes?.hipoteses.map((h) => (
              <article key={h.nome} className="app-hipotese">
                <p className="app-hipotese-nome">{h.nome}</p>
                {h.a_favor.length > 0 && (
                  <>
                    <p className="app-hipotese-rotulo">O que apoia</p>
                    <ul>
                      {h.a_favor.map((x) => (
                        <li key={x}>{x}</li>
                      ))}
                    </ul>
                  </>
                )}
                {h.contra.length > 0 && (
                  <>
                    <p className="app-hipotese-rotulo">O que afasta</p>
                    <ul>
                      {h.contra.map((x) => (
                        <li key={x}>{x}</li>
                      ))}
                    </ul>
                  </>
                )}
              </article>
            ))}
          </div>
        </div>
      </section>

      {sessao.anamnese && (
        <details className="app-recolhivel">
          <summary>Anamnese estruturada</summary>
          <dl className="app-anamnese">
            {CAMPOS_ANAMNESE.map(({ campo, rotulo }) => (
              <div key={campo}>
                <dt>{rotulo}</dt>
                <dd>{sessao.anamnese?.[campo]}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}

      <section className="app-secao app-acoes-finais" aria-label="Próximos passos">
        <button
          className="al-botao al-botao-principal app-botao-largo"
          type="button"
          onClick={() => navegar("/sessao/nova")}
        >
          Trocar de papel e gravar de novo
        </button>

        {!confirmarExclusao ? (
          <button
            className="al-botao al-botao-secundario app-botao-largo"
            type="button"
            onClick={() => setConfirmarExclusao(true)}
          >
            Excluir sessão
          </button>
        ) : (
          <div className="app-confirmar" role="alertdialog" aria-labelledby="titulo-excluir">
            <p className="app-aviso-titulo" id="titulo-excluir">
              Excluir esta sessão?
            </p>
            <p>Isso apaga a transcrição, a correção e os aceites do termo. Não dá para desfazer.</p>
            {erroExclusao && <Aviso tipo="erro">{erroExclusao}</Aviso>}
            <div className="app-acoes">
              <button
                className="al-botao al-botao-secundario app-botao-perigo"
                type="button"
                onClick={() => void excluir()}
                disabled={excluindo}
              >
                {excluindo ? "Excluindo…" : "Sim, excluir"}
              </button>
              <button
                className="al-botao al-botao-texto"
                type="button"
                onClick={() => setConfirmarExclusao(false)}
                disabled={excluindo}
              >
                Cancelar
              </button>
            </div>
          </div>
        )}
      </section>
    </Tela>
  );
}
