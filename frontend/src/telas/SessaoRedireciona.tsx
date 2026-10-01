import { Navigate, useParams } from "react-router-dom";
import { Aviso } from "../componentes/Aviso";
import { Carregando, Tela } from "../componentes/Tela";
import { rotaDaSessao, useSessao } from "../util/sessao";

/** /sessao/:id leva para a etapa em que a sessão está. */
export function SessaoRedireciona() {
  const { id } = useParams();
  const { sessao, erro } = useSessao(id);
  if (!id) return <Navigate to="/" replace />;
  if (sessao) return <Navigate to={rotaDaSessao(sessao)} replace />;
  return (
    <Tela titulo="Sessão" voltar="/" rotuloVoltar="Voltar ao início">
      {erro ? <Aviso tipo="erro">{erro}</Aviso> : <Carregando texto="Abrindo a sessão…" />}
    </Tela>
  );
}
