import { useEffect, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import { api, textoDoErro } from "../api/cliente";
import type { Fala, PapelFala } from "../api/tipos";
import { Aviso } from "../componentes/Aviso";
import { Carregando, Tela } from "../componentes/Tela";
import { rotaDaSessao, useSessao } from "../util/sessao";
import { useNavegar } from "../util/movimento";

const PAPEIS: { valor: PapelFala; rotulo: string }[] = [
  { valor: "entrevistador", rotulo: "Entrevistador" },
  { valor: "paciente", rotulo: "Paciente" },
];

export function Transcricao() {
  const { id } = useParams();
  const navegar = useNavegar();
  const { sessao, erro: erroSessao } = useSessao(id);
  const [falas, setFalas] = useState<Fala[] | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (sessao && falas === null) setFalas(sessao.falas);
  }, [sessao, falas]);

  if (!id) return <Navigate to="/" replace />;
  if (sessao && sessao.status !== "aguardando_queixa") return <Navigate to={rotaDaSessao(sessao)} replace />;

  const voltar = `/sessao/${id}/queixa`;

  const mudar = (i: number, parcial: Partial<Fala>) =>
    setFalas((fs) => fs && fs.map((f, j) => (j === i ? { ...f, ...parcial } : f)));

  const alterada =
    sessao !== null &&
    falas !== null &&
    JSON.stringify(falas) !== JSON.stringify(sessao.falas);

  const salvar = async () => {
    if (!falas) return;
    setSalvando(true);
    setErro(null);
    try {
      const limpas = falas
        .map((f) => ({ papel: f.papel, texto: f.texto.trim() }))
        .filter((f) => f.texto.length > 0);
      await api.editarTranscricao(id, { falas: limpas });
      navegar(voltar, { direcao: "voltar" });
    } catch (e) {
      setErro(textoDoErro(e));
      setSalvando(false);
    }
  };

  return (
    <Tela
      titulo="Revisar a transcrição"
      voltar={voltar}
      rotuloVoltar="Voltar para a queixa"
      rodape={
        <button
          className="al-botao al-botao-principal app-botao-largo"
          type="button"
          onClick={() => void salvar()}
          disabled={!alterada || salvando}
        >
          {salvando ? "Salvando…" : alterada ? "Salvar correções" : "Nada alterado ainda"}
        </button>
      }
    >
      {erroSessao && <Aviso tipo="erro">{erroSessao}</Aviso>}
      {!falas && !erroSessao && <Carregando texto="Carregando a transcrição…" />}

      {falas && (
        <>
          <p className="app-ajuda">
            Confira quem disse o quê e corrija palavras que a transcrição entendeu errado. A correção
            só aceita como feito o que estiver aqui. Uma fala apagada por inteiro sai da transcrição.
          </p>
          {sessao?.transcricao_editada && (
            <p className="app-legenda">Esta transcrição já foi corrigida por você.</p>
          )}
          {falas.length === 0 && <p className="app-vazio">A transcrição veio vazia.</p>}
          <ol className="app-falas">
            {falas.map((f, i) => (
              <li key={i} className={`app-fala-edicao app-fala-${f.papel}`}>
                <fieldset className="app-segmentado">
                  <legend className="app-so-leitor">Quem falou na fala {i + 1}</legend>
                  {PAPEIS.map((p) => (
                    <label key={p.valor} className={f.papel === p.valor ? "is-marcada" : ""}>
                      <input
                        type="radio"
                        name={`papel-${i}`}
                        value={p.valor}
                        checked={f.papel === p.valor}
                        onChange={() => mudar(i, { papel: p.valor })}
                      />
                      {p.rotulo}
                    </label>
                  ))}
                </fieldset>
                <label className="app-campo">
                  <span className="app-so-leitor">Texto da fala {i + 1}</span>
                  <textarea
                    value={f.texto}
                    rows={Math.min(8, Math.max(2, Math.ceil(f.texto.length / 38)))}
                    onChange={(e) => mudar(i, { texto: e.target.value })}
                  />
                </label>
              </li>
            ))}
          </ol>
          {erro && <Aviso tipo="erro">{erro}</Aviso>}
        </>
      )}
    </Tela>
  );
}
