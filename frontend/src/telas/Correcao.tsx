import { useCallback, useId, useRef, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
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
import { Avatar } from "../componentes/Avatar";
import { BarraProgresso } from "../componentes/BarraProgresso";
import { Folha } from "../componentes/Folha";
import { IconeArco, IconeAviso, IconeBalao, IconeCasa, IconeCheck, IconeLampada, IconeTrocar } from "../componentes/Icones";
import { ItemChecklist, ItemSugestao } from "../componentes/ItemChecklist";
import { Recado } from "../componentes/Recado";
import { Selo } from "../componentes/Selo";
import { Contador } from "../componentes/Contador";
import { Carregando, Tela } from "../componentes/Tela";
import { formatarRelativo, humanizar, normalizar } from "../util/formato";
import { guardarNomes, nomesDaSessao } from "../util/nomes";
import { nomesDasQueixas, rotaDaSessao, useQueixas, useSessao } from "../util/sessao";
import { movimentoReduzido, useNavegar, vibrar } from "../util/movimento";

const ID_GERAL = "geral";

type ParteDoCaso = "historia_da_doenca" | "antecedentes" | "medicacoes" | "alergias" | "habitos" | "familia" | "vida_social";

/** Partes da ficha do paciente pela IA, mostradas depois da correção. */
const CAMPOS_CASO: { campo: ParteDoCaso; rotulo: string }[] = [
  { campo: "historia_da_doenca", rotulo: "História da doença" },
  { campo: "antecedentes", rotulo: "Antecedentes" },
  { campo: "medicacoes", rotulo: "Medicações" },
  { campo: "alergias", rotulo: "Alergias" },
  { campo: "habitos", rotulo: "Hábitos" },
  { campo: "familia", rotulo: "Família" },
  { campo: "vida_social", rotulo: "Vida social" },
];

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

interface Grupo {
  checklistId: string;
  usado: ChecklistUsado | undefined;
  feitos: Avaliacao[];
  faltou: Avaliacao[];
}

function agrupar(sessao: Sessao): Grupo[] {
  const ordem = sessao.checklists_usados.map((c) => c.id);
  for (const a of sessao.avaliacoes) if (!ordem.includes(a.checklist_id)) ordem.push(a.checklist_id);

  return ordem
    .map((checklistId) => {
      const doChecklist = sessao.avaliacoes.filter((x) => x.checklist_id === checklistId);
      // Item contestado sobe para o topo dos feitos: o aluno vê o resultado na hora.
      const feitos = doChecklist
        .filter((a) => a.status === "feito")
        .sort((a, b) => Number(Boolean(b.contestacao)) - Number(Boolean(a.contestacao)));
      return {
        checklistId,
        usado: sessao.checklists_usados.find((c) => c.id === checklistId),
        feitos,
        faltou: doChecklist.filter((a) => a.status === "faltou"),
      };
    })
    .filter((g) => g.feitos.length > 0 || g.faltou.length > 0);
}

/** Junta os pontos numa frase só, com um ponto final (sem repetir o de cada ponto). */
function frase(pontos: string[]): string {
  const texto = pontos.map((p) => p.trim().replace(/[.;]+$/, "")).join("; ");
  return `${texto}.`;
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

const MOTIVOS = [
  { valor: "perguntei", rotulo: "Eu perguntei. Está na transcrição." },
  { valor: "nao-vale", rotulo: "Esse item não vale para este caso." },
  { valor: "outro", rotulo: "Outro motivo" },
] as const;

type Motivo = (typeof MOTIVOS)[number]["valor"];

interface PropsContestar {
  sessao: Sessao;
  item: Avaliacao;
  onFechar: () => void;
  onAtualizada: (s: Sessao) => void;
}

function FolhaContestar({ sessao, item, onFechar, onAtualizada }: PropsContestar) {
  const [motivo, setMotivo] = useState<Motivo>("perguntei");
  const [detalhe, setDetalhe] = useState("");
  const [indiceFala, setIndiceFala] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const rotulo = MOTIVOS.find((m) => m.valor === motivo)?.rotulo ?? "";
  const texto = motivo === "outro" ? detalhe.trim() : detalhe.trim() ? `${rotulo} ${detalhe.trim()}` : rotulo;

  const enviar = async () => {
    setEnviando(true);
    setErro(null);
    const fala = motivo === "perguntei" && indiceFala !== "" ? sessao.falas[Number(indiceFala)] : undefined;
    try {
      const nova = await api.contestar(sessao.id, {
        item_id: item.item_id,
        motivo: texto,
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
    <Folha titulo="Contestar item" subtitulo={item.texto} onFechar={onFechar}>
      <form
        className="app-grupo"
        onSubmit={(e) => {
          e.preventDefault();
          void enviar();
        }}
      >
        <fieldset className="app-grupo">
          <legend className="app-campo-rotulo">Por quê?</legend>
          <div className="app-opcoes">
            {MOTIVOS.map((m) => (
              <label key={m.valor} className={`app-opcao${motivo === m.valor ? " is-marcada" : ""}`}>
                <input
                  type="radio"
                  name={`${idBase}-motivo`}
                  checked={motivo === m.valor}
                  onChange={() => setMotivo(m.valor)}
                />
                <span className="app-opcao-rotulo">{m.rotulo}</span>
              </label>
            ))}
          </div>
        </fieldset>

        {motivo === "perguntei" && (
          <label className="app-campo" htmlFor={`${idBase}-trecho`}>
            <span className="app-campo-rotulo">Qual fala mostra isso?</span>
            <select id={`${idBase}-trecho`} value={indiceFala} onChange={(e) => setIndiceFala(e.target.value)}>
              <option value="">Não sei: mandar para o professor</option>
              {sessao.falas.map((f, i) => (
                <option key={i} value={String(i)}>
                  {f.papel === "entrevistador" ? "Você: " : "Paciente: "}
                  {f.texto.length > 90 ? `${f.texto.slice(0, 90)}…` : f.texto}
                </option>
              ))}
            </select>
          </label>
        )}

        <label className="app-campo" htmlFor={`${idBase}-detalhe`}>
          <span className="app-campo-rotulo">
            {motivo === "outro" ? "Conte o motivo" : "Quer explicar? (opcional)"}
          </span>
          <textarea
            id={`${idBase}-detalhe`}
            rows={2}
            maxLength={900}
            value={detalhe}
            onChange={(e) => setDetalhe(e.target.value)}
            required={motivo === "outro"}
          />
        </label>

        <p className="app-legenda">
          Se a fala mostrar que você investigou o item, ele conta como feito na hora. Sem fala, a
          contestação vai para o professor e a nota não muda.
        </p>
        {erro && <Aviso tipo="erro">{erro}</Aviso>}
        <button
          className="al-botao al-botao-principal app-botao-largo"
          type="submit"
          disabled={!texto || enviando}
        >
          {enviando ? "Enviando…" : "Enviar contestação"}
        </button>
      </form>
    </Folha>
  );
}

interface PropsChecklist {
  grupo: Grupo;
  sessao: Sessao;
  queixas: Queixa[];
  onContestar: (item: Avaliacao) => void;
}

const FEITOS_VISIVEIS = 3;
const PESO_IMPORTANTE = 3;
const FALTOU_MINIMO = 3;

/**
 * O que faltou em duas partes: os mais importantes ficam abertos (peso 3, ou os de maior peso
 * se nenhum tem 3) e o resto fica recolhido, para o aluno saber por onde começar.
 */
function separarFaltou(faltou: Avaliacao[]): { importantes: Avaliacao[]; completar: Avaliacao[] } {
  const ordem = [...faltou].sort((a, b) => b.peso - a.peso);
  let importantes = ordem.filter((a) => a.peso >= PESO_IMPORTANTE || Boolean(a.contestacao));
  if (importantes.length === 0) importantes = ordem.slice(0, FALTOU_MINIMO);
  return { importantes, completar: ordem.filter((a) => !importantes.includes(a)) };
}

/** Um checklist corrigido: primeiro o que você fez, depois o que faltou perguntar. */
function ChecklistCorrigido({ grupo: g, sessao, queixas, onContestar }: PropsChecklist) {
  const [verFeitos, setVerFeitos] = useState(false);
  const [verCompletar, setVerCompletar] = useState(false);
  const idFeitos = useId();
  const idCompletar = useId();

  const item = (a: Avaliacao) => (
    <li key={`${a.checklist_id}:${a.item_id}`}>
      <ItemChecklist
        avaliacao={a}
        quemFalou={quemFalou(a.trecho, sessao.falas)}
        onContestar={() => onContestar(a)}
      >
        {a.contestacao && <ResultadoContestacao c={a.contestacao} />}
      </ItemChecklist>
    </li>
  );

  const primeiros = g.feitos.slice(0, FEITOS_VISIVEIS);
  const resto = g.feitos.slice(FEITOS_VISIVEIS);
  const { importantes, completar } = separarFaltou(g.faltou);

  return (
    <section className="app-secao" aria-labelledby={`chk-${g.checklistId}`}>
      <div className="app-checklist-topo">
        <h2 className="app-subtitulo" id={`chk-${g.checklistId}`}>
          {nomeDoChecklist(g.checklistId, queixas)}
        </h2>
        {g.usado && <Selo checklist={g.usado} />}
      </div>
      <p className="app-legenda">
        {/* A contagem da técnica geral já está no placar. */}
        {g.checklistId === ID_GERAL ? "" : `${contagem([...g.feitos, ...g.faltou]) || "Nenhum item conta na nota."} `}
        {g.usado ? `Versão ${g.usado.versao} do checklist.` : ""}
      </p>

      {g.feitos.length > 0 && (
        <>
          <h3 className="app-secao-titulo">O que você fez</h3>
          <ul className="app-itens app-cascata">{primeiros.map(item)}</ul>
          {resto.length > 0 && (
            <>
              <ul id={idFeitos} className="app-itens app-cascata" hidden={!verFeitos}>
                {verFeitos && resto.map(item)}
              </ul>
              <button
                className="al-botao al-botao-texto app-ver-mais"
                type="button"
                aria-expanded={verFeitos}
                aria-controls={idFeitos}
                onClick={() => setVerFeitos((v) => !v)}
              >
                {verFeitos
                  ? "Mostrar menos"
                  : resto.length === 1
                    ? "Ver mais 1 item feito"
                    : `Ver mais ${resto.length} itens feitos`}
              </button>
            </>
          )}
        </>
      )}

      <h3 className="app-secao-titulo">O que faltou perguntar</h3>
      {g.faltou.length > 0 ? (
        <>
          {completar.length > 0 && <p className="app-legenda">Primeiro, o que mais faz diferença.</p>}
          <ul className="app-itens app-cascata">{importantes.map(item)}</ul>
          {completar.length > 0 && (
            <>
              <ul id={idCompletar} className="app-itens app-cascata" hidden={!verCompletar}>
                {verCompletar && completar.map(item)}
              </ul>
              <button
                className="al-botao al-botao-texto app-ver-mais"
                type="button"
                aria-expanded={verCompletar}
                aria-controls={idCompletar}
                onClick={() => setVerCompletar((v) => !v)}
              >
                {verCompletar
                  ? "Mostrar menos"
                  : completar.length === 1
                    ? "Ver mais 1 item para completar"
                    : `Ver mais ${completar.length} itens para completar`}
              </button>
            </>
          )}
        </>
      ) : (
        <p className="app-status app-status-ok">
          <IconeCheck />
          Nenhum item faltou neste checklist.
        </p>
      )}
    </section>
  );
}

/** Nota grande da técnica geral (conta de 0 até ela) e a da queixa ao lado, nunca somadas. */
function Placar({ sessao, nomeQueixa }: { sessao: Sessao; nomeQueixa: string }) {
  const geral = sessao.notas?.geral ?? null;
  const queixa = sessao.notas?.queixa ?? null;
  const avaliacoesGerais = sessao.avaliacoes.filter((a) => a.checklist_id === ID_GERAL);
  return (
    <section className="app-placar" aria-label="Notas da sessão">
      <div className="app-placar-linha">
        <p className="app-placar-numero app-tabular">
          {geral === null ? "–" : <Contador texto={String(geral)} rotulo={`${geral} de 100`} doZero />}
        </p>
        <div className="app-placar-lado">
          <p className="app-placar-rotulo">Técnica geral</p>
          <span className="app-chip app-tabular">
            {nomeQueixa} {queixa === null ? "sem nota" : <Contador texto={String(queixa)} doZero />}
          </span>
        </div>
      </div>
      {geral !== null && <BarraProgresso valor={geral} rotulo="Técnica geral, de 0 a 100" />}
      <p className="app-legenda">
        {geral === null ? "O checklist geral ainda não conta na nota." : contagem(avaliacoesGerais)}
      </p>
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
  const navegar = useNavegar();
  const { sessao, erro: erroSessao, definir } = useSessao(id, (s) => s.status === "gerando_sugestoes");
  const { queixas } = useQueixas();
  const [contestando, setContestando] = useState<Avaliacao | null>(null);
  const [recado, setRecado] = useState<string | null>(null);
  const [confirmarExclusao, setConfirmarExclusao] = useState(false);
  const [excluindo, setExcluindo] = useState(false);
  const [erroExclusao, setErroExclusao] = useState<string | null>(null);
  const [trocando, setTrocando] = useState(false);
  const troca = useRef<HTMLDivElement>(null);
  const fecharContestar = useCallback(() => setContestando(null), []);
  const sumirRecado = useCallback(() => setRecado(null), []);

  if (!id) return <Navigate to="/" replace />;
  if (sessao && rotaDaSessao(sessao) !== `/sessao/${id}/correcao`) {
    return <Navigate to={rotaDaSessao(sessao)} replace />;
  }

  const excluir = async () => {
    setExcluindo(true);
    setErroExclusao(null);
    try {
      await api.excluirSessao(id);
      navegar("/", { replace: true, direcao: "voltar" });
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
  const rascunhos = sessao.checklists_usados.filter((c) => c.status === "rascunho");
  const sugestoes = sessao.sugestoes;
  const gerando = sessao.status === "gerando_sugestoes";
  const nomes = nomesDaSessao(sessao.consentimentos);

  const aoContestado = (nova: Sessao) => {
    definir(nova);
    const c = contestando && nova.avaliacoes.find((a) => a.item_id === contestando.item_id && a.checklist_id === contestando.checklist_id)?.contestacao;
    setRecado(
      c?.resultado === "procedente"
        ? "Contestação aceita. O item contou como feito."
        : "Contestação enviada. A resposta chega aqui.",
    );
  };

  // As letras trocam de lugar sobre os círculos (a cor fica com o papel) e só então a nova sessão abre.
  const trocarPapel = () => {
    guardarNomes({ medico: nomes.paciente, paciente: nomes.medico });
    const avatares = troca.current?.querySelectorAll<HTMLElement>(".app-avatar");
    if (!avatares || avatares.length < 2 || movimentoReduzido()) {
      navegar("/sessao/nova");
      return;
    }
    const [a, b] = [avatares[0]!.getBoundingClientRect(), avatares[1]!.getBoundingClientRect()];
    troca.current?.style.setProperty("--dx", `${b.left - a.left}px`);
    vibrar(10);
    setTrocando(true);
    window.setTimeout(() => navegar("/sessao/nova"), 750);
  };

  return (
    <Tela
      titulo="Correção"
      sobretitulo={`${nomeQueixa} · ${formatarRelativo(sessao.criada_em)}`}
      voltar="/"
      rotuloVoltar="Voltar ao início"
    >
      {erroSessao && <Aviso tipo="erro">{erroSessao}</Aviso>}
      {sessao.status === "erro" && sessao.mensagem_erro && (
        <Aviso tipo="erro">{sessao.mensagem_erro} A correção abaixo continua valendo.</Aviso>
      )}

      {sessao.notas && <Placar sessao={sessao} nomeQueixa={nomeQueixa} />}

      {sessao.notas?.provisoria && (
        <Aviso>Nota provisória: os critérios ainda não foram revisados por um professor.</Aviso>
      )}
      {rascunhos.length > 0 && !sessao.notas?.provisoria && (
        <p className="app-legenda">
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
          onContestar={setContestando}
        />
      ))}

      {gerando && !sugestoes && (
        <p className="app-status" aria-live="polite">
          <IconeArco className="app-girando" />
          Preparando as hipóteses sugeridas e as perguntas para estudo…
        </p>
      )}

      {sugestoes && sugestoes.perguntas_sugeridas.length > 0 && (
        <PerguntasSugeridas perguntas={sugestoes.perguntas_sugeridas} />
      )}

      <section className="app-secao" aria-labelledby="titulo-hipoteses">
        <h2 className="app-subtitulo" id="titulo-hipoteses">
          Hipóteses
        </h2>
        <div className="app-hipoteses">
          <div className="app-cartao-branco">
            <p className="app-legenda">Suas hipóteses</p>
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
          <div className="app-hipoteses-ia">
            <p className="app-sugestao-rotulo">
              <IconeLampada />
              Hipóteses sugeridas, para estudo
            </p>
            <p className="app-legenda">Não são gabarito.</p>
            {!sugestoes && gerando && <p className="app-carregando">Preparando…</p>}
            {!sugestoes && !gerando && <p className="app-vazio">Sem hipóteses sugeridas nesta sessão.</p>}
            {sugestoes?.hipoteses.map((h) => (
              <article key={h.nome} className="app-hipotese">
                <p className="app-hipotese-nome">{h.nome}</p>
                {h.a_favor.length > 0 && (
                  <p className="app-hipotese-linha">
                    <b>Apoia:</b> {frase(h.a_favor)}
                  </p>
                )}
                {h.contra.length > 0 && (
                  <p className="app-hipotese-linha">
                    <b>Falta checar ou afasta:</b> {frase(h.contra)}
                  </p>
                )}
              </article>
            ))}
          </div>
          <p className="app-legenda app-centro">A IA nunca afirma diagnóstico.</p>
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

      {sessao.caso_ia && (
        <details className="app-recolhivel">
          <summary>O caso do paciente</summary>
          <p className="app-ajuda">
            {sessao.caso_ia.nome}, {sessao.caso_ia.idade} anos, {sessao.caso_ia.profissao}. É tudo o que a IA sabia; o
            que você não perguntou ficou fora da conversa.
          </p>
          <dl className="app-anamnese">
            {CAMPOS_CASO.map(({ campo, rotulo }) => (
              <div key={campo}>
                <dt>{rotulo}</dt>
                <dd>{sessao.caso_ia?.[campo].join(" ")}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}

      <section className="app-secao app-acoes-finais" aria-label="Próximos passos">
        {sessao.origem_caso === "paciente_ia" && (
          <button
            className="al-botao al-botao-principal app-botao-largo"
            type="button"
            onClick={() => navegar("/paciente-ia")}
          >
            <IconeBalao />
            Treinar com outro paciente
          </button>
        )}
        {nomes.medico && nomes.paciente && (
          <div className={`app-troca${trocando ? " is-trocando" : ""}`} ref={troca} aria-hidden="true">
            <span className="app-troca-pessoa">
              <Avatar nome={nomes.medico} papel="medico" tamanho={40} />
              Faz o médico
            </span>
            <IconeTrocar />
            <span className="app-troca-pessoa">
              <Avatar nome={nomes.paciente} papel="paciente" tamanho={40} />
              Faz o paciente
            </span>
          </div>
        )}
        {sessao.origem_caso !== "paciente_ia" && (
          <button
            className="al-botao al-botao-principal app-botao-largo"
            type="button"
            onClick={trocarPapel}
            disabled={trocando}
          >
            <IconeTrocar />
            Trocar de papel e gravar
          </button>
        )}
        <button
          className="al-botao al-botao-secundario app-botao-largo"
          type="button"
          onClick={() => navegar("/", { direcao: "voltar" })}
        >
          <IconeCasa />
          Voltar ao início
        </button>

        {!confirmarExclusao ? (
          <button
            className="al-botao al-botao-texto app-botao-largo"
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

      {contestando && (
        <FolhaContestar sessao={sessao} item={contestando} onFechar={fecharContestar} onAtualizada={aoContestado} />
      )}
      {recado && <Recado texto={recado} onSumir={sumirRecado} />}
    </Tela>
  );
}
