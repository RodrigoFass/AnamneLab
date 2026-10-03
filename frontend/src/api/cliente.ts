import { tokenAtual } from "../auth/supabase";
import type {
  Cartao,
  Consentimento,
  ConsentimentoCriar,
  ContestacaoCriar,
  HipotesesAluno,
  Queixa,
  QueixaConfirmar,
  Saude,
  Sessao,
  SessaoCriar,
  SessaoResumo,
  Termo,
  TranscricaoEditar,
} from "./tipos";

const BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? "").replace(/\/$/, "");

/** Erro vindo da API, com a mensagem do backend (campo "detail") pronta para mostrar. */
export class ErroApi extends Error {
  readonly status: number;

  constructor(mensagem: string, status: number) {
    super(mensagem);
    this.name = "ErroApi";
    this.status = status;
  }
}

interface ItemValidacao {
  msg?: string;
  loc?: (string | number)[];
}

function mensagemDoDetail(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  // Erro de validação do FastAPI: lista de itens com "msg".
  if (Array.isArray(detail) && detail.length > 0) {
    const itens = (detail as ItemValidacao[])
      .map((d) => (typeof d.msg === "string" ? d.msg : null))
      .filter((m): m is string => Boolean(m));
    if (itens.length > 0) return `Alguns dados não passaram na conferência: ${itens.join("; ")}.`;
  }
  if (status === 401) return "Sua sessão de login expirou. Entre de novo.";
  if (status === 403) return "Você não tem acesso a esta sessão.";
  if (status === 404) return "Não encontramos o que você procurou. Talvez a sessão tenha sido excluída.";
  if (status === 413) return "A gravação ficou grande demais. O limite é de 25 MB.";
  if (status >= 500) return "O servidor teve um problema. Tente de novo em alguns instantes.";
  return "Algo não saiu como esperado. Tente de novo.";
}

async function requisitar<T>(caminho: string, init: RequestInit = {}, comoArquivo = false): Promise<T> {
  const cabecalhos = new Headers(init.headers);
  if (!comoArquivo) cabecalhos.set("Accept", "application/json");
  if (init.body && !(init.body instanceof FormData)) {
    cabecalhos.set("Content-Type", "application/json");
  }
  const token = await tokenAtual();
  if (token) cabecalhos.set("Authorization", `Bearer ${token}`);

  let resposta: Response;
  try {
    resposta = await fetch(`${BASE}/api${caminho}`, { ...init, headers: cabecalhos });
  } catch {
    throw new ErroApi("Não deu para falar com o servidor. Confira a conexão e tente de novo.", 0);
  }

  if (!resposta.ok) {
    let detail: unknown = null;
    try {
      detail = ((await resposta.json()) as { detail?: unknown }).detail;
    } catch {
      // corpo sem JSON: usa a mensagem padrão do status
    }
    throw new ErroApi(mensagemDoDetail(detail, resposta.status), resposta.status);
  }

  if (resposta.status === 204) return undefined as T;
  if (comoArquivo) return (await resposta.blob()) as T;
  return (await resposta.json()) as T;
}

function json(metodo: string, corpo: unknown): RequestInit {
  return { method: metodo, body: JSON.stringify(corpo) };
}

/** Texto curto para mostrar ao aluno a partir de qualquer erro. */
export function textoDoErro(erro: unknown): string {
  if (erro instanceof ErroApi) return erro.message;
  return "Algo não saiu como esperado. Tente de novo.";
}

export const api = {
  saude: () => requisitar<Saude>("/saude"),
  queixas: () => requisitar<Queixa[]>("/queixas"),
  sortearCartao: (queixa?: string) =>
    requisitar<Cartao>(
      `/cartoes/sortear${queixa ? `?queixa=${encodeURIComponent(queixa)}` : ""}`,
    ),
  termo: () => requisitar<Termo>("/termo"),

  sessoes: () => requisitar<SessaoResumo[]>("/sessoes"),
  criarSessao: (dados: SessaoCriar) => requisitar<Sessao>("/sessoes", json("POST", dados)),
  sessao: (id: string) => requisitar<Sessao>(`/sessoes/${encodeURIComponent(id)}`),
  excluirSessao: (id: string) =>
    requisitar<void>(`/sessoes/${encodeURIComponent(id)}`, { method: "DELETE" }),

  registrarConsentimento: (id: string, dados: ConsentimentoCriar) =>
    requisitar<Consentimento>(
      `/sessoes/${encodeURIComponent(id)}/consentimentos`,
      json("POST", dados),
    ),
  enviarAudio: (id: string, audio: Blob, nomeArquivo: string) => {
    const corpo = new FormData();
    corpo.append("audio", audio, nomeArquivo);
    return requisitar<Sessao>(`/sessoes/${encodeURIComponent(id)}/audio`, {
      method: "POST",
      body: corpo,
    });
  },
  perguntarAoPaciente: (id: string, texto: string) =>
    requisitar<Sessao>(`/sessoes/${encodeURIComponent(id)}/conversa`, json("POST", { texto })),
  perguntarFalando: (id: string, audio: Blob, nomeArquivo: string) => {
    const corpo = new FormData();
    corpo.append("audio", audio, nomeArquivo);
    return requisitar<Sessao>(`/sessoes/${encodeURIComponent(id)}/conversa/audio`, { method: "POST", body: corpo });
  },
  examinarPaciente: (id: string, texto: string) =>
    requisitar<Sessao>(`/sessoes/${encodeURIComponent(id)}/exame`, json("POST", { texto })),
  examinarFalando: (id: string, audio: Blob, nomeArquivo: string) => {
    const corpo = new FormData();
    corpo.append("audio", audio, nomeArquivo);
    return requisitar<Sessao>(`/sessoes/${encodeURIComponent(id)}/exame/audio`, { method: "POST", body: corpo });
  },
  /** WAV da fala `indice` do paciente pela IA, com a voz do Piper. */
  vozDoPaciente: (id: string, indice: number) =>
    requisitar<Blob>(`/sessoes/${encodeURIComponent(id)}/voz/${indice}`, {}, true),
  encerrarConversa: (id: string) =>
    requisitar<Sessao>(`/sessoes/${encodeURIComponent(id)}/encerrar`, { method: "POST" }),
  editarTranscricao: (id: string, dados: TranscricaoEditar) =>
    requisitar<Sessao>(`/sessoes/${encodeURIComponent(id)}/transcricao`, json("PUT", dados)),
  confirmarQueixa: (id: string, dados: QueixaConfirmar) =>
    requisitar<Sessao>(`/sessoes/${encodeURIComponent(id)}/queixa`, json("POST", dados)),
  enviarHipoteses: (id: string, dados: HipotesesAluno) =>
    requisitar<Sessao>(`/sessoes/${encodeURIComponent(id)}/hipoteses`, json("POST", dados)),
  contestar: (id: string, dados: ContestacaoCriar) =>
    requisitar<Sessao>(`/sessoes/${encodeURIComponent(id)}/contestacoes`, json("POST", dados)),
};
