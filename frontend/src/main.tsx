import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { registerSW } from "virtual:pwa-register";
import { rotas } from "./App";
import { ProvedorAuth } from "./auth/Autenticacao";
import { ProvedorTema } from "./util/tema";
import "./marca/bundle.css";
import "./marca/tokens.css";
import "./app.css";

registerSW({ immediate: true });

// Roteador de dados: é ele que faz a transição de tela (View Transitions) nos links.
const roteador = createBrowserRouter(rotas);

const raiz = document.getElementById("raiz");
if (!raiz) throw new Error("Elemento #raiz não encontrado no index.html.");

createRoot(raiz).render(
  <StrictMode>
    <ProvedorTema>
      <ProvedorAuth>
        <RouterProvider router={roteador} />
      </ProvedorAuth>
    </ProvedorTema>
  </StrictMode>,
);
