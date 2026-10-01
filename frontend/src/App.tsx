import { Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/Autenticacao";
import { AvisoDemonstracao } from "./componentes/AvisoDemonstracao";
import { Carregando } from "./componentes/Tela";
import { ConfirmarQueixa } from "./telas/ConfirmarQueixa";
import { Correcao } from "./telas/Correcao";
import { Gravar } from "./telas/Gravar";
import { Hipoteses } from "./telas/Hipoteses";
import { Inicio } from "./telas/Inicio";
import { Login } from "./telas/Login";
import { NaoEncontrada } from "./telas/NaoEncontrada";
import { NovaSessao } from "./telas/NovaSessao";
import { Processando } from "./telas/Processando";
import { SessaoRedireciona } from "./telas/SessaoRedireciona";
import { Termo } from "./telas/Termo";
import { Transcricao } from "./telas/Transcricao";

export function App() {
  return (
    <>
      <AvisoDemonstracao />
      <Telas />
    </>
  );
}

function Telas() {
  const { carregando, logado } = useAuth();

  if (carregando) {
    return (
      <div className="app-tela">
        <Carregando />
      </div>
    );
  }
  if (!logado) return <Login />;

  return (
    <Routes>
      <Route path="/" element={<Inicio />} />
      <Route path="/sessao/nova" element={<NovaSessao />} />
      <Route path="/sessao/:id" element={<SessaoRedireciona />} />
      <Route path="/sessao/:id/termo" element={<Termo />} />
      <Route path="/sessao/:id/gravar" element={<Gravar />} />
      <Route path="/sessao/:id/processando" element={<Processando />} />
      <Route path="/sessao/:id/queixa" element={<ConfirmarQueixa />} />
      <Route path="/sessao/:id/transcricao" element={<Transcricao />} />
      <Route path="/sessao/:id/hipoteses" element={<Hipoteses />} />
      <Route path="/sessao/:id/correcao" element={<Correcao />} />
      <Route path="*" element={<NaoEncontrada />} />
    </Routes>
  );
}
