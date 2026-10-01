import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { registerSW } from "virtual:pwa-register";
import { App } from "./App";
import { ProvedorAuth } from "./auth/Autenticacao";
import { ProvedorTema } from "./util/tema";
import "./marca/bundle.css";
import "./marca/tokens.css";
import "./app.css";

registerSW({ immediate: true });

const raiz = document.getElementById("raiz");
if (!raiz) throw new Error("Elemento #raiz não encontrado no index.html.");

createRoot(raiz).render(
  <StrictMode>
    <ProvedorTema>
      <ProvedorAuth>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ProvedorAuth>
    </ProvedorTema>
  </StrictMode>,
);
