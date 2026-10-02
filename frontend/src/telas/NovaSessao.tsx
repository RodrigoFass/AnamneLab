import { useState, type PointerEvent, type ReactNode } from "react";
import { api, textoDoErro } from "../api/cliente";
import type { Cartao, OrigemCaso, Papel } from "../api/tipos";
import { Aviso } from "../componentes/Aviso";
import { Avatar } from "../componentes/Avatar";
import { CartaoPaciente } from "../componentes/CartaoPaciente";
import { IconeDado, IconeGlobo, IconeLapis, IconeLivro } from "../componentes/Icones";
import { Tela } from "../componentes/Tela";
import { guardarNomes, lerNomes, type Nomes } from "../util/nomes";
import { usePerfil } from "../util/perfil";
import { useQueixas } from "../util/sessao";
import { useNavegar, vibrar } from "../util/movimento";

const ORIGENS: { valor: OrigemCaso; rotulo: string; icone: ReactNode }[] = [
  { valor: "livro", rotulo: "Livro", icone: <IconeLivro /> },
  { valor: "internet", rotulo: "Internet", icone: <IconeGlobo /> },
  { valor: "inventado", rotulo: "Inventado", icone: <IconeLapis /> },
  { valor: "cartao", rotulo: "Sortear cartão", icone: <IconeDado /> },
];

const AJUDA_ORIGEM: Record<OrigemCaso, string> = {
  livro: "Um caso clínico de livro ou apostila. O app não guarda o texto do caso.",
  internet: "Um caso que vocês acharam on-line. O app não guarda o texto do caso.",
  inventado: "Quem faz o paciente cria o caso na hora.",
  cartao: "O app sorteia um ponto de partida. Só quem faz o paciente olha o cartão.",
};

const PAPEIS: { papel: Papel; rotulo: string }[] = [
  { papel: "medico", rotulo: "Faz o médico" },
  { papel: "paciente", rotulo: "Faz o paciente" },
];

export function NovaSessao() {
  const navegar = useNavegar();
  const { queixas } = useQueixas();
  const perfil = usePerfil();
  // Na primeira sessão da aba, quem usa o app faz o médico; dá para trocar.
  const [nomes, setNomes] = useState<Nomes>(() => {
    const n = lerNomes();
    return n.medico || n.paciente ? n : { ...n, medico: perfil.nome };
  });
  const [origem, setOrigem] = useState<OrigemCaso | null>(null);
  const [filtroQueixa, setFiltroQueixa] = useState("");
  const [cartao, setCartao] = useState<Cartao | null>(null);
  const [cartaoVisivel, setCartaoVisivel] = useState(false);
  const [sorteando, setSorteando] = useState(false);
  const [criando, setCriando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const sortear = async () => {
    setSorteando(true);
    setErro(null);
    try {
      setCartao(await api.sortearCartao(filtroQueixa || undefined));
    } catch (e) {
      setErro(textoDoErro(e));
    } finally {
      setSorteando(false);
    }
  };

  // O preenchimento da opção nasce do ponto tocado (revelação radial).
  const marcarToque = (e: PointerEvent<HTMLLabelElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty("--x", `${e.clientX - r.left}px`);
    e.currentTarget.style.setProperty("--y", `${e.clientY - r.top}px`);
  };

  const escolherOrigem = (valor: OrigemCaso) => {
    vibrar(6);
    setOrigem(valor);
    setErro(null);
    if (valor !== "cartao") {
      setCartao(null);
      setCartaoVisivel(false);
    }
  };

  const continuar = async () => {
    if (!origem) return;
    setCriando(true);
    setErro(null);
    guardarNomes({ medico: nomes.medico.trim(), paciente: nomes.paciente.trim() });
    try {
      const sessao = await api.criarSessao({
        origem_caso: origem,
        cartao_id: origem === "cartao" ? (cartao?.id ?? null) : null,
      });
      navegar(`/sessao/${sessao.id}/termo`);
    } catch (e) {
      setErro(textoDoErro(e));
      setCriando(false);
    }
  };

  const podeContinuar = origem !== null && (origem !== "cartao" || cartao !== null);

  return (
    <Tela
      titulo="Nova sessão"
      voltar="/"
      rodape={
        <button
          className="al-botao al-botao-principal app-botao-largo"
          type="button"
          onClick={() => void continuar()}
          disabled={!podeContinuar || criando}
        >
          {criando ? "Abrindo a sessão…" : "Continuar"}
        </button>
      }
    >
      <fieldset className="app-grupo">
        <legend className="app-subtitulo">Quem faz o quê</legend>
        <div className="app-dupla">
          {PAPEIS.map(({ papel, rotulo }) => (
            <label key={papel} className="app-pessoa">
              <Avatar nome={nomes[papel]} papel={papel} />
              <span className="app-pessoa-texto">
                <input
                  className="app-pessoa-nome"
                  type="text"
                  autoComplete="off"
                  maxLength={120}
                  placeholder="Nome"
                  aria-label={`Nome de quem ${rotulo.toLowerCase()}`}
                  value={nomes[papel]}
                  onChange={(e) => setNomes((n) => ({ ...n, [papel]: e.target.value }))}
                />
                <span className="app-pessoa-papel">{rotulo}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="app-grupo">
        <legend className="app-subtitulo">De onde vem o caso</legend>
        <div className="app-grade-origem">
          {ORIGENS.map((o) => (
            <label
              key={o.valor}
              className={`app-origem${origem === o.valor ? " is-marcada" : ""}`}
              onPointerDown={marcarToque}
            >
              <input
                className="app-so-leitor"
                type="radio"
                name="origem"
                value={o.valor}
                checked={origem === o.valor}
                onChange={() => escolherOrigem(o.valor)}
              />
              <span className="app-origem-conteudo">
                {o.icone}
                {o.rotulo}
              </span>
            </label>
          ))}
        </div>
        <p className="app-legenda" aria-live="polite">
          {origem ? AJUDA_ORIGEM[origem] : "Use só casos simulados. Não grave pacientes reais."}
        </p>
      </fieldset>

      {origem === "cartao" && (
        <section className="app-secao app-surge" aria-label="Cartão do paciente">
          {!cartao && (
            <>
              <label className="app-campo">
                <span className="app-campo-rotulo">Queixa do cartão (opcional)</span>
                <select value={filtroQueixa} onChange={(e) => setFiltroQueixa(e.target.value)}>
                  <option value="">Qualquer queixa</option>
                  {queixas.map((q) => (
                    <option key={q.id} value={q.id}>
                      {q.nome}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="al-botao al-botao-secundario app-botao-largo"
                type="button"
                onClick={() => void sortear()}
                disabled={sorteando}
              >
                <IconeDado />
                {sorteando ? "Sorteando…" : "Sortear cartão"}
              </button>
            </>
          )}

          {cartao && (
            <div className={`app-virar${cartaoVisivel ? " is-virado" : ""}`}>
              <div className="app-virar-miolo">
                <div className="app-virar-face app-virar-costas" inert={cartaoVisivel}>
                  <span className="app-virar-dado" aria-hidden="true">
                    <IconeDado />
                  </span>
                  <p className="app-subtitulo">Cartão sorteado</p>
                  <p className="app-centro">
                    Só quem faz o paciente pode ver. Passe o celular para{" "}
                    {nomes.paciente.trim() || "o seu colega"}.
                  </p>
                  <button
                    className="al-botao al-botao-secundario"
                    type="button"
                    onClick={() => {
                      vibrar(10);
                      setCartaoVisivel(true);
                    }}
                  >
                    Sou o paciente, mostrar cartão
                  </button>
                </div>
                <div className="app-virar-face app-virar-frente" inert={!cartaoVisivel}>
                  <CartaoPaciente
                    key={cartao.id}
                    cartao={cartao}
                    nomePaciente={nomes.paciente.trim()}
                    onSortearOutro={() => void sortear()}
                    sorteando={sorteando}
                  />
                  <button
                    className="al-botao al-botao-texto app-link"
                    type="button"
                    onClick={() => setCartaoVisivel(false)}
                  >
                    Esconder o cartão
                  </button>
                </div>
              </div>
            </div>
          )}
        </section>
      )}

      {erro && <Aviso tipo="erro">{erro}</Aviso>}
    </Tela>
  );
}
