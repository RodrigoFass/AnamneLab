import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/cliente";
import type { SessaoResumo } from "../api/tipos";
import { useAuth } from "../auth/Autenticacao";
import { Avatar } from "../componentes/Avatar";
import { Contador } from "../componentes/Contador";
import { IconeCheck, IconeEngrenagem } from "../componentes/Icones";
import { Recado } from "../componentes/Recado";
import { Tela } from "../componentes/Tela";
import { retirarAceiteDoDono, useAceiteDono } from "../util/aceites";
import { formatarData } from "../util/formato";
import { useNavegar, vibrar } from "../util/movimento";
import { linhaDoPerfil, salvarPerfil, usePerfil, type Perfil as TipoPerfil } from "../util/perfil";

export const PERIODOS = ["1º", "2º", "3º", "4º", "5º", "6º", "7º", "8º", "9º", "10º", "11º", "12º"];

/** Campos do perfil, usados no cadastro e na aba Perfil. */
export function CamposPerfil({ perfil, onMudar }: { perfil: TipoPerfil; onMudar: (p: TipoPerfil) => void }) {
  return (
    <>
      <label className="app-campo">
        <span className="app-campo-rotulo">Como você se chama?</span>
        <input
          type="text"
          autoComplete="given-name"
          maxLength={60}
          value={perfil.nome}
          placeholder="Seu nome"
          onChange={(e) => onMudar({ ...perfil, nome: e.target.value })}
        />
      </label>
      <label className="app-campo">
        <span className="app-campo-rotulo">Disciplina</span>
        <input
          type="text"
          maxLength={60}
          value={perfil.disciplina}
          placeholder="Por exemplo: Semiologia"
          onChange={(e) => onMudar({ ...perfil, disciplina: e.target.value })}
        />
      </label>
      <fieldset className="app-grupo">
        <legend className="app-campo-rotulo">Em que período você está?</legend>
        <div className="app-periodos">
          {PERIODOS.map((p) => (
            <label key={p} className={`app-periodo${perfil.periodo === p ? " is-marcada" : ""}`}>
              <input
                className="app-so-leitor"
                type="radio"
                name="periodo"
                checked={perfil.periodo === p}
                onChange={() => {
                  vibrar(6);
                  onMudar({ ...perfil, periodo: p });
                }}
              />
              {p}
            </label>
          ))}
        </div>
      </fieldset>
    </>
  );
}

export function Perfil() {
  const navegar = useNavegar();
  const salvo = usePerfil();
  const { loginAtivo, email, sair } = useAuth();
  const aceite = useAceiteDono();
  const [perfil, setPerfil] = useState(salvo);
  const [recado, setRecado] = useState<string | null>(null);
  const [sessoes, setSessoes] = useState<SessaoResumo[] | null>(null);

  useEffect(() => {
    let ativo = true;
    api.sessoes().then(
      (s) => ativo && setSessoes(s),
      () => ativo && setSessoes([]),
    );
    return () => {
      ativo = false;
    };
  }, []);

  const mudou = JSON.stringify(perfil) !== JSON.stringify(salvo);
  const notas = (sessoes ?? []).map((s) => s.notas?.geral).filter((n): n is number => typeof n === "number");
  const media = notas.length ? Math.round(notas.reduce((a, b) => a + b, 0) / notas.length) : null;

  return (
    <Tela
      titulo="Perfil"
      className="app-tela-abas"
      canto={
        <Link className="app-topo-botao" to="/configuracoes" aria-label="Configurações" title="Configurações">
          <IconeEngrenagem />
        </Link>
      }
    >
      <section className="app-perfil-topo app-surge">
        <Avatar nome={salvo.nome} papel="medico" tamanho={64} />
        <div>
          <p className="app-subtitulo">{salvo.nome || "Sem nome"}</p>
          <p className="app-legenda">{linhaDoPerfil(salvo) || "Complete o seu perfil abaixo."}</p>
        </div>
      </section>

      <dl className="app-numeros app-cascata">
        <div>
          <dt>Sessões</dt>
          <dd>{sessoes ? <Contador texto={String(sessoes.length)} doZero /> : "–"}</dd>
        </div>
        <div>
          <dt>Média geral</dt>
          <dd>{media === null ? "–" : <Contador texto={String(media)} doZero />}</dd>
        </div>
        <div>
          <dt>Melhor nota</dt>
          <dd>{notas.length ? <Contador texto={String(Math.max(...notas))} doZero /> : "–"}</dd>
        </div>
      </dl>

      <form
        className="app-grupo"
        onSubmit={(e) => {
          e.preventDefault();
          salvarPerfil(perfil);
          vibrar(12);
          setRecado("Perfil salvo.");
        }}
      >
        <CamposPerfil perfil={perfil} onMudar={setPerfil} />
        <button
          className="al-botao al-botao-principal app-botao-largo"
          type="submit"
          disabled={!mudou || !perfil.nome.trim()}
        >
          {mudou ? (
            "Salvar perfil"
          ) : (
            <>
              <IconeCheck />
              Perfil salvo
            </>
          )}
        </button>
      </form>

      <section className="app-secao" aria-labelledby="titulo-termo">
        <h2 className="app-subtitulo" id="titulo-termo">
          Termo de gravação
        </h2>
        {aceite ? (
          <>
            <p className="app-ajuda">
              Você aceitou o termo (v{aceite.versao}) em {formatarData(aceite.em)}. Ele vale para as suas
              sessões neste aparelho. O colega que faz o outro papel confirma a cada gravação.
            </p>
            <button
              className="al-botao al-botao-texto app-botao-largo"
              type="button"
              onClick={() => {
                retirarAceiteDoDono();
                setRecado("Aceite retirado. O termo aparece de novo na próxima gravação.");
              }}
            >
              Retirar o aceite
            </button>
          </>
        ) : (
          <p className="app-ajuda">
            Você ainda não aceitou o termo. Ele aparece uma vez, antes da sua próxima gravação.
          </p>
        )}
      </section>

      <section className="app-secao" aria-labelledby="titulo-conta">
        <h2 className="app-subtitulo" id="titulo-conta">
          Conta
        </h2>
        {loginAtivo ? (
          <p className="app-conta">
            {email ? `Conectado como ${email}. ` : ""}
            <button className="al-botao al-botao-texto" type="button" onClick={() => void sair()}>
              Sair
            </button>
          </p>
        ) : (
          <>
            <p className="app-ajuda">
              Sem conta: o perfil e as sessões ficam neste aparelho. Com o app publicado, você entra com o
              seu e-mail.
            </p>
            <button
              className="al-botao al-botao-secundario app-botao-largo"
              type="button"
              onClick={() => navegar("/entrar")}
            >
              Ver a tela de entrar
            </button>
          </>
        )}
      </section>

      {recado && <Recado texto={recado} icone="check" onSumir={() => setRecado(null)} />}
    </Tela>
  );
}
