import { useState } from "react";
import { flushSync } from "react-dom";
import { useAuth } from "../auth/Autenticacao";
import { SeloDemonstracao } from "../componentes/AvisoDemonstracao";
import { IconeCheck, IconeLampada, IconeMicrofone, IconeSelo } from "../componentes/Icones";
import { useTema } from "../util/tema";
import { marcarDirecao, movimentoReduzido, vibrar } from "../util/movimento";
import { primeiroNome, salvarPerfil, type Perfil } from "../util/perfil";
import { CamposPerfil } from "./Perfil";

const PONTOS = [
  { icone: <IconeMicrofone />, texto: "Simulem a consulta em dupla. O celular fica entre vocês e só escuta." },
  { icone: <IconeSelo />, texto: "A correção vem item a item, e cada acerto cita a sua fala." },
  { icone: <IconeLampada />, texto: "Escreva as suas hipóteses antes e compare com as sugeridas." },
];

type Passo = "oi" | "cadastro" | "pronto";

/**
 * Primeira vez no app: boas-vindas com a marca, cadastro do perfil (nome, disciplina,
 * período) e um "pronto" com o check desenhado. Os passos deslizam para o lado.
 */
export function BoasVindas() {
  const tema = useTema();
  const { loginAtivo } = useAuth();
  const [passo, setPasso] = useState<Passo>("oi");
  const [perfil, setPerfil] = useState<Perfil>({ nome: "", disciplina: "Semiologia", periodo: "", faculdade: "", avatar: "" });

  const concluir = () => {
    vibrar([10, 60, 10]);
    setPasso("pronto");
    // Mostra o "pronto" por um instante e entra no app.
    window.setTimeout(() => {
      const salvar = () => flushSync(() => salvarPerfil(perfil));
      if (document.startViewTransition && !movimentoReduzido()) {
        marcarDirecao("avancar");
        document.startViewTransition(salvar);
      } else salvar();
    }, movimentoReduzido() ? 300 : 1300);
  };

  return (
    <div className="app-tela app-boas-vindas">
      <div className="app-topo-linha">
        <span className="app-passos" aria-hidden="true">
          <span className={passo === "oi" ? "is-ativo" : ""} />
          <span className={passo !== "oi" ? "is-ativo" : ""} />
        </span>
        <SeloDemonstracao />
      </div>

      {passo === "oi" && (
        <main className="app-conteudo app-passo" key="oi">
          <div className="app-marca-anima" aria-hidden="true">
            <img src={tema === "escuro" ? "/simbolo-escuro.svg" : "/simbolo-claro.svg"} width={72} height={72} alt="" />
          </div>
          <h1 className="app-boas-titulo">
            <span>Anamne</span>
            <b>Lab</b>
          </h1>
          <p className="app-assinatura app-revela">Pergunte melhor.</p>
          <p className="app-descritor app-revela">Treino de anamnese com correção na hora.</p>
          <ul className="app-pontos app-cascata app-cascata-lenta">
            {PONTOS.map((p) => (
              <li key={p.texto}>
                {p.icone}
                <span>{p.texto}</span>
              </li>
            ))}
          </ul>
          <div className="app-empurra" />
          <button
            className="al-botao al-botao-principal app-botao-largo app-revela-tarde"
            type="button"
            onClick={() => setPasso("cadastro")}
          >
            Começar
          </button>
          <p className="app-legenda app-centro app-revela-tarde">Use só casos simulados. Nunca grave pacientes reais.</p>
        </main>
      )}

      {passo === "cadastro" && (
        <form
          className="app-conteudo app-passo"
          key="cadastro"
          onSubmit={(e) => {
            e.preventDefault();
            concluir();
          }}
        >
          <h1 className="app-titulo">Crie o seu perfil</h1>
          <p className="app-subtitulo-tela">
            {loginAtivo
              ? "Leva meio minuto. O perfil fica na sua conta e aparece no início e na evolução."
              : "Leva meio minuto. O perfil fica neste aparelho e aparece no início e na evolução."}
          </p>
          <CamposPerfil perfil={perfil} onMudar={setPerfil} />
          <div className="app-empurra" />
          <button
            className="al-botao al-botao-principal app-botao-largo"
            type="submit"
            disabled={!perfil.nome.trim() || !perfil.periodo}
          >
            Criar perfil
          </button>
          <button className="al-botao al-botao-texto app-botao-largo" type="button" onClick={() => setPasso("oi")}>
            Voltar
          </button>
        </form>
      )}

      {passo === "pronto" && (
        <main className="app-conteudo app-pronto" key="pronto" role="status">
          <span className="app-pronto-circulo" aria-hidden="true">
            <IconeCheck className="app-check-desenha" />
          </span>
          <p className="app-boas-titulo">Tudo pronto, {primeiroNome(perfil.nome)}.</p>
          <p className="app-descritor">Chame um colega e grave a primeira sessão.</p>
        </main>
      )}
    </div>
  );
}
