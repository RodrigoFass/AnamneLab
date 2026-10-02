/** 0 a 3599 s -> "mm:ss"; acima disso, "h:mm:ss". */
export function formatarTempo(segundos: number): string {
  const s = Math.max(0, Math.floor(segundos));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(r).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

const formatoData = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** "01 de out. de 2026, 14:32" */
export function formatarData(iso: string): string {
  const data = new Date(iso);
  if (Number.isNaN(data.getTime())) return "";
  return formatoData.format(data);
}

/** Normaliza texto para comparar trechos: minúsculas, sem acento, espaços simples. */
export function normalizar(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[“”"'‘’.,;:!?…()-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Primeira letra maiúscula e hífens viram espaço ("inicio-e-duracao" -> "Inicio e duracao"). */
export function humanizar(texto: string): string {
  const limpo = /\s/.test(texto) ? texto : texto.replace(/[-_]+/g, " ");
  return limpo.charAt(0).toUpperCase() + limpo.slice(1);
}

/** "hoje", "ontem", "há 3 dias", "há 2 semanas"; mais de um mês, a data curta. */
export function formatarRelativo(iso: string, agora = new Date()): string {
  const data = new Date(iso);
  if (Number.isNaN(data.getTime())) return "";
  const meiaNoite = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const dias = Math.round((meiaNoite(agora) - meiaNoite(data)) / 86_400_000);
  if (dias <= 0) return "hoje";
  if (dias === 1) return "ontem";
  if (dias < 7) return `há ${dias} dias`;
  if (dias < 30) {
    const semanas = Math.floor(dias / 7);
    return semanas === 1 ? "há 1 semana" : `há ${semanas} semanas`;
  }
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short" }).format(data);
}
