import { Outlet, useLocation, type RouteObject } from "react-router-dom";
import { useAuth } from "./auth/Autenticacao";
import { Abas } from "./componentes/Abas";
import { ProvedorDemonstracao } from "./componentes/AvisoDemonstracao";
import { Carregando } from "./componentes/Tela";
import { BoasVindas } from "./telas/BoasVindas";
import { Evolucao } from "./telas/Evolucao";
import { Perfil } from "./telas/Perfil";
import { Configuracoes } from "./telas/Configuracoes";
import { ConfirmarQueixa } from "./telas/ConfirmarQueixa";
import { Correcao } from "./telas/Correcao";
import { Gravar } from "./telas/Gravar";
import { Hipoteses } from "./telas/Hipoteses";
import { Inicio } from "./telas/Inicio";
import { Login, NovaSenha } from "./telas/Login";
import { NaoEncontrada } from "./telas/NaoEncontrada";
import { NovaSessao } from "./telas/NovaSessao";
import { Processando } from "./telas/Processando";
import { SessaoRedireciona } from "./telas/SessaoRedireciona";
import { Termo } from "./telas/Termo";
import { Transcricao } from "./telas/Transcricao";
import { usePerfil } from "./util/perfil";

/**
 * Rotas do roteador de dados (createBrowserRouter). Ficam todas aqui, num nível só,
 * para os links terem transição de tela: rotas dentro de <Routes> perdem a View Transition.
 */
export const rotas: RouteObject[] = [
  {
    element: <App />,
    children: [
      {
        // As três abas dividem a mesma barra, que fica montada entre elas: o fundo da aba ativa desliza.
        element: <ComAbas />,
        children: [
          { path: "/", element: <Inicio /> },
          { path: "/evolucao", element: <Evolucao /> },
          { path: "/perfil", element: <Perfil /> },
        ],
      },
      { path: "/configuracoes", element: <Configuracoes /> },
      { path: "/sessao/nova", element: <NovaSessao /> },
      { path: "/sessao/:id", element: <SessaoRedireciona /> },
      { path: "/sessao/:id/termo", element: <Termo /> },
      { path: "/sessao/:id/gravar", element: <Gravar /> },
      { path: "/sessao/:id/processando", element: <Processando /> },
      { path: "/sessao/:id/queixa", element: <ConfirmarQueixa /> },
      { path: "/sessao/:id/transcricao", element: <Transcricao /> },
      { path: "/sessao/:id/hipoteses", element: <Hipoteses /> },
      { path: "/sessao/:id/correcao", element: <Correcao /> },
      { path: "*", element: <NaoEncontrada /> },
    ],
  },
];

function App() {
  return (
    <ProvedorDemonstracao>
      <Telas />
    </ProvedorDemonstracao>
  );
}

function ComAbas() {
  return (
    <>
      <Outlet />
      <Abas />
    </>
  );
}

function Telas() {
  const { carregando, logado, loginAtivo, recuperandoSenha } = useAuth();
  const perfil = usePerfil();
  const { pathname } = useLocation();

  if (carregando) {
    return (
      <div className="app-tela">
        <Carregando />
      </div>
    );
  }
  if (!logado) return <Login />;
  if (recuperandoSenha) return <NovaSenha />;
  // Sem login (demonstração), /entrar mostra a tela de entrar só para ver o visual.
  if (!loginAtivo && pathname === "/entrar") return <Login />;
  if (!perfil.nome) return <BoasVindas />;

  return <Outlet />;
}
