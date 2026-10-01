import { useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { api, textoDoErro } from "../api/cliente";
import type { Sessao } from "../api/tipos";
import { Aviso } from "../componentes/Aviso";
import { BarraProgresso } from "../componentes/BarraProgresso";
import { IconeArco } from "../componentes/Icones";
import { Carregando, Tela } from "../componentes/Tela";
import { rotaDaSessao, useSessao } from "../util/sessao";

function etapa(s: Sessao): string {
  if (s.progresso < 45) return "Transcrevendo a conversa…";
  if (s.progresso < 75) return "Separando o que cada um falou…";
  return "Procurando a queixa principal…";
}

export function Processando() {
  const { id } = useParams();
  const navegar = useNavigate();
  const { sessao, erro } = useSessao(id, (s) => s.status === "processando_audio");
  const [recomecando, setRecomecando] = useState(false);
  const [erroRecomecar, setErroRecomecar] = useState<string | null>(null);

  if (!id) return <Navigate to="/" replace />;
  if (sessao && rotaDaSessao(sessao) !== `/sessao/${id}/processando`) {
    return <Navigate to={rotaDaSessao(sessao)} replace />;
  }

  // Gravar de novo abre uma sessão nova com o mesmo caso: o termo é aceito de novo.
  const gravarDeNovo = async () => {
    if (!sessao) return;
    setRecomecando(true);
    setErroRecomecar(null);
    try {
      const nova = await api.criarSessao({
        origem_caso: sessao.origem_caso,
        cartao_id: sessao.cartao_id,
      });
      navegar(`/sessao/${nova.id}/termo`, { replace: true });
    } catch (e) {
      setErroRecomecar(textoDoErro(e));
      setRecomecando(false);
    }
  };

  if (sessao?.status === "erro") {
    return (
      <Tela titulo="Não deu para corrigir" voltar="/" rotuloVoltar="Voltar ao início">
        <Aviso tipo="erro" titulo="O que aconteceu">
          {sessao.mensagem_erro ?? "Algo não saiu como esperado no processamento."}
        </Aviso>
        <p>O áudio desta tentativa já foi apagado. Vocês podem gravar de novo com o mesmo caso.</p>
        {erroRecomecar && <Aviso tipo="erro">{erroRecomecar}</Aviso>}
        <div className="app-acoes">
          <button
            className="al-botao al-botao-principal"
            type="button"
            onClick={() => void gravarDeNovo()}
            disabled={recomecando}
          >
            {recomecando ? "Abrindo nova sessão…" : "Gravar de novo"}
          </button>
          <button className="al-botao al-botao-texto" type="button" onClick={() => navegar("/")}>
            Voltar ao início
          </button>
        </div>
      </Tela>
    );
  }

  return (
    <Tela titulo="Processando a gravação">
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      {!sessao && !erro && <Carregando />}
      {sessao && (
        <section className="app-processando">
          <p className="app-status" aria-live="polite">
            <IconeArco className="app-girando" />
            {etapa(sessao)}
          </p>
          <BarraProgresso valor={sessao.progresso} rotulo="Progresso do processamento" />
          <p className="app-legenda app-tabular">{Math.round(sessao.progresso)}%</p>
          <p className="app-ajuda">
            Isso leva de um a três minutos. O áudio é apagado assim que a transcrição termina. Pode
            deixar esta tela aberta.
          </p>
        </section>
      )}
    </Tela>
  );
}
