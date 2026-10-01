import { useCallback, useEffect, useState, type Dispatch, type SetStateAction } from "react";
import { api, textoDoErro } from "../api/cliente";
import type { Queixa, Sessao, StatusSessao } from "../api/tipos";

export const INTERVALO_CONSULTA_MS = 2000;

/** Para onde o aluno deve ir, dado o estado da sessão. */
export function rotaDaSessao(
  s: Pick<Sessao, "id" | "status" | "consentimentos" | "hipoteses_aluno" | "avaliacoes">,
): string {
  const base = `/sessao/${s.id}`;
  switch (s.status) {
    case "criada": {
      const papeis = new Set(s.consentimentos.map((c) => c.papel));
      return papeis.has("medico") && papeis.has("paciente") ? `${base}/gravar` : `${base}/termo`;
    }
    case "erro":
      // Falha nas sugestões, depois das hipóteses: a correção já existe e continua visível.
      return s.hipoteses_aluno.length > 0 && s.avaliacoes.length > 0 ? `${base}/correcao` : `${base}/processando`;
    case "processando_audio":
      return `${base}/processando`;
    case "aguardando_queixa":
      return `${base}/queixa`;
    case "corrigindo":
    case "aguardando_hipoteses":
      return `${base}/hipoteses`;
    case "gerando_sugestoes":
    case "concluida":
      return `${base}/correcao`;
  }
}

export const STATUS_EM_ANDAMENTO: StatusSessao[] = [
  "processando_audio",
  "corrigindo",
  "gerando_sugestoes",
];

interface EstadoSessao {
  sessao: Sessao | null;
  erro: string | null;
  carregando: boolean;
  recarregar: () => Promise<void>;
  /** Troca o estado local, por exemplo com a resposta de um POST. */
  definir: Dispatch<SetStateAction<Sessao | null>>;
}

/**
 * Busca a sessão e, enquanto `consultarEnquanto` for verdadeiro para o estado atual,
 * consulta de novo a cada 2 s.
 */
export function useSessao(
  id: string | undefined,
  consultarEnquanto: (s: Sessao) => boolean = () => false,
): EstadoSessao {
  const [sessao, setSessao] = useState<Sessao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  // Muda a cada resposta (mesmo com erro), para a próxima consulta ser agendada.
  const [tique, setTique] = useState(0);

  const recarregar = useCallback(async () => {
    if (!id) return;
    try {
      const s = await api.sessao(id);
      setSessao(s);
      setErro(null);
    } catch (e) {
      setErro(textoDoErro(e));
    } finally {
      setCarregando(false);
      setTique((t) => t + 1);
    }
  }, [id]);

  useEffect(() => {
    void recarregar();
  }, [recarregar]);

  const deveConsultar = sessao !== null && consultarEnquanto(sessao);

  useEffect(() => {
    if (!deveConsultar) return;
    const t = window.setTimeout(() => void recarregar(), INTERVALO_CONSULTA_MS);
    return () => window.clearTimeout(t);
  }, [deveConsultar, tique, recarregar]);

  return { sessao, erro, carregando, recarregar, definir: setSessao };
}

let cacheQueixas: Promise<Queixa[]> | null = null;

/** Biblioteca fechada de queixas, buscada uma vez por carregamento do app. */
export function useQueixas(): { queixas: Queixa[]; erro: string | null } {
  const [queixas, setQueixas] = useState<Queixa[]>([]);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;
    if (!cacheQueixas) cacheQueixas = api.queixas();
    cacheQueixas.then(
      (q) => ativo && setQueixas(q),
      (e: unknown) => {
        cacheQueixas = null;
        if (ativo) setErro(textoDoErro(e));
      },
    );
    return () => {
      ativo = false;
    };
  }, []);

  return { queixas, erro };
}

/** Nome padrão da queixa a partir do id; "outra" usa a descrição quando houver. */
export function nomeDaQueixa(
  id: string,
  queixas: Queixa[],
  descricaoOutra?: string | null,
): string {
  if (id === "outra") return descricaoOutra ? `Outra: ${descricaoOutra}` : "Outra queixa";
  return queixas.find((q) => q.id === id)?.nome ?? id;
}

/** "Dor torácica e Dispneia" */
export function nomesDasQueixas(
  ids: string[],
  queixas: Queixa[],
  descricaoOutra?: string | null,
): string {
  const nomes = ids.map((id) => nomeDaQueixa(id, queixas, descricaoOutra));
  if (nomes.length <= 1) return nomes[0] ?? "";
  return `${nomes.slice(0, -1).join(", ")} e ${nomes[nomes.length - 1]}`;
}
