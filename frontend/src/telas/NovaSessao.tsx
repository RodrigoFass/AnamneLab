import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api, textoDoErro } from "../api/cliente";
import type { Cartao, OrigemCaso, Papel } from "../api/tipos";
import { Aviso } from "../componentes/Aviso";
import { Avatar } from "../componentes/Avatar";
import { CartaoPaciente } from "../componentes/CartaoPaciente";
import { IconeDado, IconeGlobo, IconeLapis, IconeLivro } from "../componentes/Icones";
import { Tela } from "../componentes/Tela";
import { guardarNomes, lerNomes, type Nomes } from "../util/nomes";
import { useQueixas } from "../util/sessao";

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
  const navegar = useNavigate();
  const { queixas } = useQueixas();
  const [nomes, setNomes] = useState<Nomes>(lerNomes);
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

  const escolherOrigem = (valor: OrigemCaso) => {
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
            <label key={o.valor} className={`app-origem${origem === o.valor ? " is-marcada" : ""}`}>
              <input
                className="app-so-leitor"
                type="radio"
                name="origem"
                value={o.valor}
                checked={origem === o.valor}
                onChange={() => escolherOrigem(o.valor)}
              />
              {o.icone}
              {o.rotulo}
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

          {cartao && !cartaoVisivel && (
            <div className="app-cartao-oculto">
              <p>
                Cartão sorteado. Só quem faz o paciente pode ver: passe o celular para{" "}
                {nomes.paciente.trim() || "o seu colega"}.
              </p>
              <button
                className="al-botao al-botao-secundario"
                type="button"
                onClick={() => setCartaoVisivel(true)}
              >
                Sou o paciente, mostrar cartão
              </button>
            </div>
          )}

          {cartao && cartaoVisivel && (
            <>
              <CartaoPaciente
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
            </>
          )}
        </section>
      )}

      {erro && <Aviso tipo="erro">{erro}</Aviso>}
    </Tela>
  );
}
