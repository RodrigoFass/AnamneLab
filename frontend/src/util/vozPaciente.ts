import { api } from "../api/cliente";
import type { Sexo } from "../api/tipos";

/**
 * Voz do paciente pela IA.
 *
 * Com o Piper no backend (GET /api/saude traz `vozes_paciente`), a fala vem pronta em WAV.
 * Sem ele, quem fala é o navegador (speechSynthesis), com uma voz em português do aparelho.
 * A ordem: Piper do mesmo sexo, voz do navegador, Piper do outro sexo. Sem nenhuma, o aluno
 * só lê a resposta.
 */

const FEMININAS =
  /maria|francisca|luciana|vit[oó]ria|fernanda|raquel|joana|catarina|helena|thalita|leila|yara|brenda|giovanna|let[ií]cia|manuela|elza|google portugu[eê]s do brasil/i;
const MASCULINAS = /daniel|ant[oô]nio|felipe|f[aá]bio|j[uú]lio|donato|nicolau|humberto|val[eé]rio|duarte|cristiano/i;

let tocador: HTMLAudioElement | null = null;
let terminarAtual: (() => void) | null = null;
const cacheWav = new Map<string, string>();

/** Libera o som no primeiro toque: celulares só tocam áudio que começou num gesto. */
export function destravarSom(): void {
  if (!tocador) {
    tocador = new Audio();
    tocador.preload = "auto";
  }
  try {
    if (typeof speechSynthesis !== "undefined" && !speechSynthesis.speaking) {
      speechSynthesis.speak(new SpeechSynthesisUtterance(""));
    }
  } catch {
    // Sem voz do navegador: segue sem ela.
  }
}

export function pararVoz(): void {
  if (tocador) {
    tocador.pause();
    tocador.removeAttribute("src");
  }
  try {
    if (typeof speechSynthesis !== "undefined") speechSynthesis.cancel();
  } catch {
    // nada a parar
  }
  terminarAtual?.();
  terminarAtual = null;
}

async function vozesDoNavegador(): Promise<SpeechSynthesisVoice[]> {
  if (typeof speechSynthesis === "undefined") return [];
  let vozes = speechSynthesis.getVoices();
  if (vozes.length === 0) {
    // Chrome carrega a lista depois.
    await new Promise<void>((pronto) => {
      const fim = window.setTimeout(pronto, 1000);
      speechSynthesis.addEventListener(
        "voiceschanged",
        () => {
          window.clearTimeout(fim);
          pronto();
        },
        { once: true },
      );
    });
    vozes = speechSynthesis.getVoices();
  }
  return vozes.filter((v) => v.lang.toLowerCase().startsWith("pt"));
}

function escolherVoz(vozes: SpeechSynthesisVoice[], sexo: Sexo): SpeechSynthesisVoice | undefined {
  const brasil = vozes.filter((v) => v.lang.toLowerCase().replace("_", "-") === "pt-br");
  const nome = sexo === "feminino" ? FEMININAS : MASCULINAS;
  for (const lista of [brasil, vozes]) {
    const certa = lista.find((v) => nome.test(v.name));
    if (certa) return certa;
  }
  return brasil[0] ?? vozes[0];
}

/** True se o navegador tem alguma voz em português. */
export async function navegadorFalaPortugues(): Promise<boolean> {
  return (await vozesDoNavegador()).length > 0;
}

function tocarWav(url: string): Promise<void> {
  if (!tocador) tocador = new Audio();
  const audio = tocador;
  return new Promise<void>((pronto, falhou) => {
    const terminar = () => {
      audio.onended = null;
      audio.onerror = null;
      terminarAtual = null;
      pronto();
    };
    terminarAtual = terminar;
    audio.onended = terminar;
    audio.onerror = () => {
      terminarAtual = null;
      falhou(new Error("áudio"));
    };
    audio.src = url;
    audio.play().catch(falhou);
  });
}

function falarNoNavegador(texto: string, voz: SpeechSynthesisVoice): Promise<void> {
  return new Promise<void>((pronto) => {
    const fala = new SpeechSynthesisUtterance(texto);
    fala.voice = voz;
    fala.lang = voz.lang;
    fala.rate = 1;
    const terminar = () => {
      terminarAtual = null;
      pronto();
    };
    terminarAtual = terminar;
    fala.onend = terminar;
    fala.onerror = terminar;
    speechSynthesis.cancel();
    speechSynthesis.speak(fala);
  });
}

interface Fala {
  sessaoId: string;
  /** Posição da fala na lista de falas da sessão. */
  indice: number;
  texto: string;
  sexo: Sexo;
  /** Sexos com voz do Piper no backend. */
  piper: Sexo[];
}

/**
 * Fala a resposta do paciente e resolve quando termina. Devolve false quando não há voz
 * em português neste aparelho nem no backend.
 */
export async function falarPaciente({ sessaoId, indice, texto, sexo, piper }: Fala): Promise<boolean> {
  pararVoz();
  const vozes = await vozesDoNavegador();
  const daNavegador = vozes.length > 0 ? escolherVoz(vozes, sexo) : undefined;
  const usarPiper = piper.includes(sexo) || (!daNavegador && piper.length > 0);
  if (usarPiper) {
    const chave = `${sessaoId}:${indice}`;
    try {
      let url = cacheWav.get(chave);
      if (!url) {
        url = URL.createObjectURL(await api.vozDoPaciente(sessaoId, indice));
        cacheWav.set(chave, url);
      }
      await tocarWav(url);
      return true;
    } catch {
      // Piper fora do ar ou som bloqueado: tenta a voz do navegador.
    }
  }
  if (!daNavegador) return false;
  await falarNoNavegador(texto, daNavegador);
  return true;
}
