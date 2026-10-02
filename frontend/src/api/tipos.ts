// Espelho dos modelos do backend:
//   backend/app/schemas/llm.py
//   backend/app/schemas/sessao.py
//   backend/app/schemas/conteudo.py (Queixa e Cartao)
// Mudou lá, muda aqui. Datas (datetime) chegam como texto ISO 8601.

// ---------- llm.py ----------

export type PapelFala = "entrevistador" | "paciente";

export interface Fala {
  papel: PapelFala;
  texto: string;
}

export interface AnamneseEstruturada {
  identificacao: string;
  queixa_principal: string;
  hda: string;
  interrogatorio_sintomatologico: string;
  antecedentes_pessoais: string;
  antecedentes_familiares: string;
  habitos_de_vida: string;
  condicoes_socioeconomicas: string;
}

export interface HipoteseIA {
  nome: string;
  a_favor: string[];
  contra: string[];
}

/** Hipóteses sugeridas para estudo (nunca diagnóstico) e perguntas fora da nota. */
export interface SugestoesIA {
  hipoteses: HipoteseIA[];
  perguntas_sugeridas: string[];
}

// ---------- conteudo.py ----------

export interface Queixa {
  id: string;
  nome: string;
  sinonimos: string[];
  checklist: string | null;
}

export type Sexo = "feminino" | "masculino";

export interface Cartao {
  id: string;
  queixa: string;
  idade: number;
  sexo: Sexo;
  resumo: string;
  detalhes: string[];
}

// ---------- sessao.py ----------

export type OrigemCaso = "livro" | "internet" | "inventado" | "cartao";
export type Papel = "medico" | "paciente";

export type StatusSessao =
  | "criada"
  | "processando_audio"
  | "aguardando_queixa"
  | "corrigindo"
  | "aguardando_hipoteses"
  | "gerando_sugestoes"
  | "concluida"
  | "erro";

export type StatusItem = "feito" | "faltou";

// entrada

export interface SessaoCriar {
  origem_caso: OrigemCaso;
  cartao_id?: string | null;
}

/** `aceite`: a pessoa aceitou o termo. `declarado_pelo_dono`: quem abriu a sessão avisou o colega. */
export type FormaConsentimento = "aceite" | "declarado_pelo_dono";

export interface ConsentimentoCriar {
  papel: Papel;
  nome_informado: string;
  versao_termo: string;
  aceito: true;
  forma?: FormaConsentimento;
}

export interface TranscricaoEditar {
  falas: Fala[];
}

export interface QueixaConfirmar {
  /** Ids da biblioteca, ou ["outra"]. */
  queixas: string[];
  descricao_outra?: string | null;
  /** Sem o campo, fica o detectado na conversa; null é "não sei". */
  sexo_paciente?: Sexo | null;
}

export interface HipotesesAluno {
  hipoteses: string[];
}

export interface ContestacaoCriar {
  item_id: string;
  motivo: string;
  /** Fala da transcrição que o aluno aponta como prova. */
  trecho?: string | null;
}

// saída

/** Resposta de GET /api/saude. */
export interface Saude {
  ok: boolean;
  /** LLM ou transcrição falsos: a interface avisa em todas as telas. */
  modo_demonstracao: boolean;
}

export interface Termo {
  versao: string;
  titulo: string;
  texto: string;
}

export interface Consentimento {
  id: string;
  sessao_id: string;
  papel: Papel;
  nome_informado: string;
  versao_termo: string;
  aceito_em: string;
  forma: FormaConsentimento;
}

export interface ChecklistUsado {
  id: string;
  versao: number;
  status: "rascunho" | "aprovado";
  conta_na_nota: boolean;
}

export type ResultadoContestacao = "procedente" | "pendente_professor";

export interface Contestacao {
  item_id: string;
  motivo: string;
  trecho: string | null;
  resultado: ResultadoContestacao;
  criada_em: string;
}

/** Um item corrigido. O trecho só existe se foi conferido na transcrição. */
export interface Avaliacao {
  item_id: string;
  checklist_id: string;
  secao: string;
  texto: string;
  status: StatusItem;
  trecho: string | null;
  /** Feito: o que o aluno fez. Faltou: a frase "faltou" do checklist. */
  mensagem: string;
  peso: number;
  conta_na_nota: boolean;
  contestacao: Contestacao | null;
}

export interface Notas {
  /** Técnica geral, 0 a 100. Nulo se o checklist geral não conta na nota. */
  geral: number | null;
  /** Específica da queixa, 0 a 100. Nulo se não há checklist da queixa que conte. */
  queixa: number | null;
  /** True quando entrou checklist em rascunho na conta (CONTAR_RASCUNHO=true). */
  provisoria: boolean;
}

export interface Sessao {
  id: string;
  dono_id: string;
  criada_em: string;
  status: StatusSessao;
  /** 0 a 100, para a barra de progresso. */
  progresso: number;
  mensagem_erro: string | null;
  origem_caso: OrigemCaso;
  cartao_id: string | null;
  consentimentos: Consentimento[];
  falas: Fala[];
  transcricao_editada: boolean;
  queixa_detectada: string[];
  queixa_trecho: string | null;
  queixas_confirmadas: string[];
  descricao_outra: string | null;
  /** Detectado na conversa e confirmado com a queixa. */
  sexo_paciente: Sexo | null;
  checklists_usados: ChecklistUsado[];
  anamnese: AnamneseEstruturada | null;
  hipoteses_aluno: string[];
  /** Só é preenchido na resposta depois que o aluno enviou as hipóteses. */
  avaliacoes: Avaliacao[];
  notas: Notas | null;
  sugestoes: SugestoesIA | null;
}

export interface SessaoResumo {
  id: string;
  criada_em: string;
  status: StatusSessao;
  queixas_confirmadas: string[];
  notas: Notas | null;
}
