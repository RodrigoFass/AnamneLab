import { useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { api, textoDoErro } from "../api/cliente";
import type { QueixaConfirmar } from "../api/tipos";
import { Aviso } from "../componentes/Aviso";
import { Avatar } from "../componentes/Avatar";
import { Etapas } from "../componentes/Etapas";
import { QueixaDetectada } from "../componentes/QueixaDetectada";
import { Carregando, Tela } from "../componentes/Tela";
import { nomesDaSessao } from "../util/nomes";
import { nomesDasQueixas, rotaDaSessao, useQueixas, useSessao } from "../util/sessao";
import { etapasDoAudio } from "./Processando";
import { useNavegar } from "../util/movimento";

export function ConfirmarQueixa() {
  const { id } = useParams();
  const navegar = useNavegar();
  const { sessao, erro: erroSessao } = useSessao(id);
  const { queixas, erro: erroQueixas } = useQueixas();

  const [trocando, setTrocando] = useState(false);
  const [marcadas, setMarcadas] = useState<string[]>([]);
  const [outra, setOutra] = useState(false);
  const [descricao, setDescricao] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  if (!id) return <Navigate to="/" replace />;
  if (sessao && sessao.status !== "aguardando_queixa") return <Navigate to={rotaDaSessao(sessao)} replace />;

  const detectada = sessao?.queixa_detectada ?? [];
  const semDeteccao = sessao !== null && detectada.length === 0;
  const mostrarLista = trocando || semDeteccao;

  const enviar = async (dados: QueixaConfirmar) => {
    setEnviando(true);
    setErro(null);
    try {
      await api.confirmarQueixa(id, dados);
      navegar(`/sessao/${id}/hipoteses`, { replace: true });
    } catch (e) {
      setErro(textoDoErro(e));
      setEnviando(false);
    }
  };

  const confirmarDetectada = () =>
    void enviar({
      queixas: detectada,
      descricao_outra: detectada.includes("outra") ? (sessao?.descricao_outra ?? null) : null,
    });

  const abrirTroca = () => {
    setTrocando(true);
    setMarcadas(detectada.filter((q) => q !== "outra"));
    setOutra(detectada.includes("outra"));
    setDescricao(sessao?.descricao_outra ?? "");
  };

  const alternarQueixa = (qid: string, marcada: boolean) => {
    setOutra(false);
    setMarcadas((m) => (marcada ? [...m, qid] : m.filter((x) => x !== qid)));
  };

  const confirmarTroca = () => {
    if (outra) void enviar({ queixas: ["outra"], descricao_outra: descricao.trim() });
    else void enviar({ queixas: marcadas, descricao_outra: null });
  };

  const trocaValida = outra ? descricao.trim().length > 0 : marcadas.length > 0;

  return (
    <Tela
      titulo="Preparando sua correção"
      subtitulo="Confira a queixa: com a queixa errada, o checklist também fica errado."
      voltar="/"
      rotuloVoltar="Voltar ao início"
    >
      {(erroSessao ?? erroQueixas) && <Aviso tipo="erro">{erroSessao ?? erroQueixas}</Aviso>}
      {!sessao && !erroSessao && <Carregando />}

      {sessao && (
        <>
          <Etapas etapas={etapasDoAudio(sessao)} />

          {sessao.falas.length > 0 && (
            <section className="app-trecho" aria-label="Trecho da transcrição">
              <p className="app-legenda">Trecho da transcrição, falas separadas</p>
              <ul className="app-falas-curtas app-cascata">
                {sessao.falas.slice(0, 2).map((f, i) => {
                  const nomes = nomesDaSessao(sessao.consentimentos);
                  const papel = f.papel === "entrevistador" ? "medico" : "paciente";
                  return (
                    <li key={i}>
                      <Avatar nome={nomes[papel]} papel={papel} tamanho={22} />
                      <span>{f.texto}</span>
                    </li>
                  );
                })}
              </ul>
            </section>
          )}

          {!semDeteccao && !trocando && (
            <QueixaDetectada
              nome={nomesDasQueixas(detectada, queixas, sessao.descricao_outra)}
              trecho={sessao.queixa_trecho}
              onConfirmar={confirmarDetectada}
              onTrocar={abrirTroca}
              confirmando={enviando}
            />
          )}

          {semDeteccao && (
            <Aviso>Não deu para identificar a queixa na conversa. Escolha na lista abaixo.</Aviso>
          )}

          {mostrarLista && (
            <fieldset className="app-grupo">
              <legend className="app-subtitulo">Qual foi a queixa principal?</legend>
              <p className="app-ajuda">Pode marcar mais de uma, se o paciente trouxe duas.</p>
              <div className="app-opcoes">
                {queixas.map((q) => (
                  <label key={q.id} className={`app-opcao${marcadas.includes(q.id) ? " is-marcada" : ""}`}>
                    <input
                      type="checkbox"
                      checked={marcadas.includes(q.id)}
                      onChange={(e) => alternarQueixa(q.id, e.target.checked)}
                    />
                    <span className="app-opcao-rotulo">{q.nome}</span>
                  </label>
                ))}
                <label className={`app-opcao${outra ? " is-marcada" : ""}`}>
                  <input
                    type="checkbox"
                    checked={outra}
                    onChange={(e) => {
                      setOutra(e.target.checked);
                      if (e.target.checked) setMarcadas([]);
                    }}
                  />
                  <span>
                    <span className="app-opcao-rotulo">Outra</span>
                    <span className="app-opcao-ajuda">
                      Não está na lista. A correção usa só o checklist geral.
                    </span>
                  </span>
                </label>
              </div>
              {outra && (
                <label className="app-campo">
                  <span className="app-campo-rotulo">Qual foi a queixa?</span>
                  <input
                    type="text"
                    maxLength={200}
                    value={descricao}
                    onChange={(e) => setDescricao(e.target.value)}
                    placeholder="Por exemplo: zumbido no ouvido"
                  />
                </label>
              )}
              <div className="app-acoes">
                <button
                  className="al-botao al-botao-principal"
                  type="button"
                  disabled={!trocaValida || enviando}
                  onClick={confirmarTroca}
                >
                  {enviando ? "Confirmando…" : "Confirmar queixa"}
                </button>
                {trocando && !semDeteccao && (
                  <button
                    className="al-botao al-botao-texto"
                    type="button"
                    onClick={() => setTrocando(false)}
                    disabled={enviando}
                  >
                    Cancelar
                  </button>
                )}
              </div>
            </fieldset>
          )}

          {erro && <Aviso tipo="erro">{erro}</Aviso>}

          <Link className="al-botao al-botao-texto app-link" to={`/sessao/${id}/transcricao`}>
            Revisar a transcrição
          </Link>
        </>
      )}
    </Tela>
  );
}
