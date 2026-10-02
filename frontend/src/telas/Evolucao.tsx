import { useEffect, useState } from "react";
import { api, textoDoErro } from "../api/cliente";
import type { Sessao, SessaoResumo } from "../api/tipos";
import { Aviso } from "../componentes/Aviso";
import { GraficoEvolucao } from "../componentes/GraficoEvolucao";
import { IconeMicrofone, IconeX } from "../componentes/Icones";
import { Carregando, Tela } from "../componentes/Tela";
import { formatarRelativo } from "../util/formato";
import { useNavegar } from "../util/movimento";

const ULTIMAS = 6;

interface Esquecido {
  texto: string;
  vezes: number;
  de: number;
}

/** Item de checklist que mais faltou nas sessões, contando uma vez por sessão. */
function maisEsquecido(sessoes: Sessao[]): Esquecido | null {
  const contas = new Map<string, { texto: string; vezes: number }>();
  for (const s of sessoes) {
    const vistos = new Set<string>();
    for (const a of s.avaliacoes) {
      const chave = `${a.checklist_id}:${a.item_id}`;
      if (a.status !== "faltou" || !a.conta_na_nota || vistos.has(chave)) continue;
      vistos.add(chave);
      const c = contas.get(chave) ?? { texto: a.texto, vezes: 0 };
      c.vezes += 1;
      contas.set(chave, c);
    }
  }
  let melhor: Esquecido | null = null;
  for (const c of contas.values()) {
    if (!melhor || c.vezes > melhor.vezes) melhor = { ...c, de: sessoes.length };
  }
  return melhor && melhor.vezes > 1 ? melhor : null;
}

export function Evolucao() {
  const navegar = useNavegar();
  const [resumos, setResumos] = useState<SessaoResumo[] | null>(null);
  const [esquecido, setEsquecido] = useState<Esquecido | null | undefined>(undefined);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;
    api
      .sessoes()
      .then(async (s) => {
        if (!ativo) return;
        const comNota = s.filter((x) => typeof x.notas?.geral === "number").slice(0, ULTIMAS);
        setResumos(comNota);
        // O resumo não traz os itens: busca as sessões com nota para achar o mais esquecido.
        const completas = await Promise.all(comNota.map((x) => api.sessao(x.id)));
        if (ativo) setEsquecido(maisEsquecido(completas));
      })
      .catch((e: unknown) => ativo && setErro(textoDoErro(e)));
    return () => {
      ativo = false;
    };
  }, []);

  const pontos = (resumos ?? [])
    .slice()
    .reverse()
    .map((s, i, todos) => ({
      nota: s.notas?.geral as number,
      rotulo: i === todos.length - 1 ? formatarRelativo(s.criada_em) : `${i + 1}ª`,
    }));

  return (
    <Tela
      titulo="Sua evolução"
      subtitulo={
        resumos && resumos.length > 1 ? `Técnica geral nas últimas ${resumos.length} sessões` : "Técnica geral por sessão"
      }
      className="app-tela-abas"
    >
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      {!resumos && !erro && <Carregando texto="Carregando a sua evolução…" />}

      {resumos && resumos.length < 2 && (
        <section className="app-vazio-cartao app-surge">
          <p className="app-subtitulo">
            {resumos.length === 0 ? "Nenhuma sessão corrigida ainda" : "Falta uma sessão para o gráfico"}
          </p>
          <p className="app-ajuda">
            O gráfico aparece a partir da segunda sessão corrigida. Cada ponto é a sua nota de técnica geral.
          </p>
        </section>
      )}

      {pontos.length > 1 && <GraficoEvolucao pontos={pontos} />}

      {esquecido && (
        <section className="app-esquecido app-surge" aria-labelledby="titulo-esquecido">
          <p className="app-esquecido-rotulo" id="titulo-esquecido">
            <IconeX />
            Mais esquecido
          </p>
          <p>
            {esquecido.texto}, em {esquecido.vezes} das {esquecido.de} sessões.
          </p>
        </section>
      )}

      <button
        className="al-botao al-botao-principal app-botao-largo"
        type="button"
        onClick={() => navegar("/sessao/nova")}
      >
        <IconeMicrofone />
        Começar sessão
      </button>
    </Tela>
  );
}
