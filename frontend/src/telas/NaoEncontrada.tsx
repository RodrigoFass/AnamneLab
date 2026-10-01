import { Link } from "react-router-dom";
import { Tela } from "../componentes/Tela";

export function NaoEncontrada() {
  return (
    <Tela titulo="Página não encontrada" voltar="/" rotuloVoltar="Voltar ao início">
      <p>Este endereço não leva a nenhuma tela do AnamneLab.</p>
      <Link className="al-botao al-botao-principal app-botao-largo" to="/">
        Voltar ao início
      </Link>
    </Tela>
  );
}
