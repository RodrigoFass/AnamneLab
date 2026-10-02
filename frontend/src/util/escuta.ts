/**
 * Escuta contínua para a consulta por voz: o microfone fica ligado e o app percebe sozinho
 * quando o aluno começa e quando termina uma pergunta, pelo volume da voz acima do ruído do
 * ambiente. A pergunta sai em WAV mono de 16 kHz, o formato que o Whisper usa.
 *
 * Enquanto o paciente pensa e fala, a escuta fica pausada, para não ouvir a voz dele.
 */

/** Fala mais curta que isso é tosse, clique ou ruído. */
const VOZ_MINIMA_MS = 300;
/** Voz seguida por este tempo marca o começo da fala. */
const COMECO_MS = 120;
/** Silêncio por este tempo marca o fim da pergunta. */
const PAUSA_FIM_MS = 900;
/** Áudio guardado antes do começo detectado, para não cortar a primeira sílaba. */
const ANTES_MS = 400;
const FALA_MAXIMA_MS = 60_000;
const TAXA_SAIDA = 16_000;

interface Eventos {
  /** O aluno começou a falar. */
  onComeco: () => void;
  /** A pergunta terminou: o WAV vai para a transcrição. A escuta pausa até `retomar()`. */
  onPergunta: (wav: Blob) => void;
  /** Volume de 0 a 1, várias vezes por segundo, para animar a tela. */
  onNivel: (nivel: number) => void;
}

export class Escuta {
  private contexto: AudioContext | null = null;
  private fluxo: MediaStream | null = null;
  private processador: ScriptProcessorNode | null = null;
  private fonte: MediaStreamAudioSourceNode | null = null;
  private ouvindo = false;
  private mudo = false;
  private piso = 0.004;
  private falando = false;
  private vozSeguidaMs = 0;
  private vozTotalMs = 0;
  private silencioMs = 0;
  private duracaoMs = 0;
  private antes: Float32Array[] = [];
  private blocos: Float32Array[] = [];

  constructor(private readonly eventos: Eventos) {}

  /** Liga o microfone. Precisa vir de um toque do aluno (permissão e áudio no celular). */
  async iniciar(): Promise<void> {
    this.fluxo = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    const Contexto =
      window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    this.contexto = new Contexto();
    await this.contexto.resume();
    this.fonte = this.contexto.createMediaStreamSource(this.fluxo);
    this.processador = this.contexto.createScriptProcessor(2048, 1, 1);
    this.processador.onaudioprocess = (e) => this.bloco(e.inputBuffer.getChannelData(0));
    this.fonte.connect(this.processador);
    // O processador só roda ligado à saída; ele não escreve nada nela (silêncio).
    this.processador.connect(this.contexto.destination);
    this.ouvindo = true;
  }

  /** Volta a ouvir depois da resposta do paciente. */
  retomar(): void {
    this.zerar();
    this.ouvindo = true;
  }

  pausar(): void {
    this.ouvindo = false;
    this.zerar();
  }

  mutar(mudo: boolean): void {
    this.mudo = mudo;
    if (mudo) this.zerar();
  }

  parar(): void {
    this.ouvindo = false;
    this.processador?.disconnect();
    this.fonte?.disconnect();
    this.fluxo?.getTracks().forEach((t) => t.stop());
    void this.contexto?.close().catch(() => undefined);
    this.contexto = null;
    this.fluxo = null;
  }

  private zerar(): void {
    this.falando = false;
    this.vozSeguidaMs = 0;
    this.vozTotalMs = 0;
    this.silencioMs = 0;
    this.duracaoMs = 0;
    this.antes = [];
    this.blocos = [];
  }

  private bloco(dados: Float32Array): void {
    if (!this.contexto) return;
    let soma = 0;
    for (let i = 0; i < dados.length; i++) soma += dados[i]! * dados[i]!;
    const volume = Math.sqrt(soma / dados.length);
    const ms = (dados.length / this.contexto.sampleRate) * 1000;
    this.eventos.onNivel(this.ouvindo && !this.mudo ? Math.min(1, volume * 12) : 0);
    if (!this.ouvindo || this.mudo) return;

    const limiar = Math.max(this.piso * 3.5, 0.012);
    const voz = volume > limiar;
    const copia = new Float32Array(dados);

    if (!this.falando) {
      // O piso acompanha o ruído do ambiente: desce na hora e sobe devagar.
      this.piso = volume < this.piso ? volume : Math.min(this.piso * 1.01, 0.05);
      this.antes.push(copia);
      while (this.antes.length * ms > ANTES_MS) this.antes.shift();
      this.vozSeguidaMs = voz ? this.vozSeguidaMs + ms : 0;
      if (this.vozSeguidaMs >= COMECO_MS) {
        this.falando = true;
        this.blocos = this.antes;
        this.antes = [];
        this.vozTotalMs = this.vozSeguidaMs;
        this.duracaoMs = this.blocos.length * ms;
        this.silencioMs = 0;
        this.eventos.onComeco();
      }
      return;
    }

    this.blocos.push(copia);
    this.duracaoMs += ms;
    if (voz) {
      this.silencioMs = 0;
      this.vozTotalMs += ms;
    } else {
      this.silencioMs += ms;
    }
    if (this.silencioMs >= PAUSA_FIM_MS || this.duracaoMs >= FALA_MAXIMA_MS) this.terminar();
  }

  private terminar(): void {
    const blocos = this.blocos;
    const vozTotal = this.vozTotalMs;
    const taxa = this.contexto?.sampleRate ?? 48_000;
    this.zerar();
    if (vozTotal < VOZ_MINIMA_MS) return; // continua ouvindo
    this.ouvindo = false;
    this.eventos.onPergunta(paraWav(juntar(blocos), taxa));
  }
}

function juntar(blocos: Float32Array[]): Float32Array {
  const total = blocos.reduce((n, b) => n + b.length, 0);
  const saida = new Float32Array(total);
  let pos = 0;
  for (const b of blocos) {
    saida.set(b, pos);
    pos += b.length;
  }
  return saida;
}

/** Reduz para 16 kHz (média de cada janela) e grava PCM de 16 bits. */
function paraWav(amostras: Float32Array, taxa: number): Blob {
  const passo = taxa / TAXA_SAIDA;
  const n = Math.floor(amostras.length / passo);
  const dados = new DataView(new ArrayBuffer(44 + n * 2));
  const texto = (pos: number, s: string) => {
    for (let i = 0; i < s.length; i++) dados.setUint8(pos + i, s.charCodeAt(i));
  };
  texto(0, "RIFF");
  dados.setUint32(4, 36 + n * 2, true);
  texto(8, "WAVE");
  texto(12, "fmt ");
  dados.setUint32(16, 16, true);
  dados.setUint16(20, 1, true);
  dados.setUint16(22, 1, true);
  dados.setUint32(24, TAXA_SAIDA, true);
  dados.setUint32(28, TAXA_SAIDA * 2, true);
  dados.setUint16(32, 2, true);
  dados.setUint16(34, 16, true);
  texto(36, "data");
  dados.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) {
    const de = Math.floor(i * passo);
    const ate = Math.min(amostras.length, Math.floor((i + 1) * passo));
    let soma = 0;
    for (let j = de; j < ate; j++) soma += amostras[j]!;
    const v = Math.max(-1, Math.min(1, soma / Math.max(1, ate - de)));
    dados.setInt16(44 + i * 2, v < 0 ? v * 0x8000 : v * 0x7fff, true);
  }
  return new Blob([dados], { type: "audio/wav" });
}
