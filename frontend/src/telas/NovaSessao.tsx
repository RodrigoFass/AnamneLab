import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, textoDoErro } from "../api/cliente";
import type { Cartao, OrigemCaso } from "../api/tipos";
import { Aviso } from "../componentes/Aviso";
import { CartaoPaciente } from "../componentes/CartaoPaciente";
import { IconeDado } from "../componentes/Icones";
import { Tela } from "../componentes/Tela";
import { useQueixas } from "../util/sessao";

const ORIGENS: { valor: OrigemCaso; rotulo: string; ajuda: string }[] = [
  { valor: "livro", rotulo: "De um livro", ajuda: "Um caso clínico de livro ou apostila." },
  { valor: "internet", rotulo: "Da internet", ajuda: "Um caso que vocês acharam on-line." },
  { valor: "inventado", rotulo: "Inventado", ajuda: "Quem faz o paciente cria o caso na hora." },
  { valor: "cartao", rotulo: "Cartão sorteado", ajuda: "O app sorteia um ponto de partida para o paciente." },
];

export function NovaSessao() {
  const navegar = useNavigate();
  const { queixas } = useQueixas();
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
          {criando ? "Abrindo a sessão…" : "Continuar para o termo"}
        </button>
      }
    >
      <Aviso titulo="Antes de tudo">Use só casos simulados. Não grave pacientes reais.</Aviso>

      <fieldset className="app-grupo">
        <legend className="app-subtitulo">De onde vem o caso?</legend>
        <p className="app-ajuda">
          O app não guarda o texto do caso, só a conversa de vocês.
        </p>
        <div className="app-opcoes">
          {ORIGENS.map((o) => (
            <label key={o.valor} className={`app-opcao${origem === o.valor ? " is-marcada" : ""}`}>
              <input
                type="radio"
                name="origem"
                value={o.valor}
                checked={origem === o.valor}
                onChange={() => escolherOrigem(o.valor)}
              />
              <span>
                <span className="app-opcao-rotulo">{o.rotulo}</span>
                <span className="app-opcao-ajuda">{o.ajuda}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      {origem === "cartao" && (
        <section className="app-secao" aria-labelledby="titulo-cartao">
          <h2 className="app-subtitulo" id="titulo-cartao">
            Cartão do paciente
          </h2>
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

          {!cartao && (
            <button
              className="al-botao al-botao-secundario app-botao-largo"
              type="button"
              onClick={() => void sortear()}
              disabled={sorteando}
            >
              <IconeDado />
              {sorteando ? "Sorteando…" : "Sortear cartão"}
            </button>
          )}

          {cartao && !cartaoVisivel && (
            <div className="app-cartao-oculto">
              <p>
                Cartão sorteado. Só quem faz o paciente pode ver: passe o celular para o seu
                colega.
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
              <CartaoPaciente cartao={cartao} onSortearOutro={() => void sortear()} sorteando={sorteando} />
              <button
                className="al-botao al-botao-texto"
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
