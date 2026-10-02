import { Tela } from "../componentes/Tela";
import { salvarPreferencias, usePreferencias, type Preferencias } from "../util/preferencias";
import { vibrar } from "../util/movimento";

interface Opcao<T> {
  valor: T;
  rotulo: string;
}

/** Um grupo de opções lado a lado, uma marcada. */
function Escolha<T extends string | boolean>({
  titulo,
  ajuda,
  nome,
  opcoes,
  valor,
  onMudar,
}: {
  titulo: string;
  ajuda?: string;
  nome: string;
  opcoes: Opcao<T>[];
  valor: T;
  onMudar: (v: T) => void;
}) {
  return (
    <fieldset className="app-grupo">
      <legend className="app-campo-rotulo">{titulo}</legend>
      <div className="app-segmentado">
        {opcoes.map((o) => (
          <label key={String(o.valor)} className={valor === o.valor ? "is-marcada" : ""}>
            <input
              type="radio"
              name={nome}
              checked={valor === o.valor}
              onChange={() => {
                onMudar(o.valor);
                vibrar(6);
              }}
            />
            {o.rotulo}
          </label>
        ))}
      </div>
      {ajuda && <p className="app-ajuda">{ajuda}</p>}
    </fieldset>
  );
}

/** Configurações do app, dentro do perfil. Mudam na hora e ficam neste aparelho. */
export function Configuracoes() {
  const p = usePreferencias();
  const mudar = (m: Partial<Preferencias>) => salvarPreferencias(m);

  return (
    <Tela titulo="Configurações" subtitulo="Mudam na hora e ficam salvas neste aparelho." voltar="/perfil">
      <section className="app-secao app-grupo">
        <h2 className="app-subtitulo">Aparência</h2>
        <Escolha
          titulo="Tema"
          nome="tema"
          valor={p.tema}
          onMudar={(tema) => mudar({ tema })}
          opcoes={[
            { valor: "automatico", rotulo: "Automático" },
            { valor: "claro", rotulo: "Claro" },
            { valor: "escuro", rotulo: "Escuro" },
          ]}
          ajuda={p.tema === "automatico" ? "Segue o tema do celular ou do computador." : undefined}
        />
        <Escolha
          titulo="Tamanho do texto"
          nome="texto"
          valor={p.texto}
          onMudar={(texto) => mudar({ texto })}
          opcoes={[
            { valor: "normal", rotulo: "Normal" },
            { valor: "grande", rotulo: "Grande" },
            { valor: "maior", rotulo: "Maior" },
          ]}
        />
      </section>

      <section className="app-secao app-grupo">
        <h2 className="app-subtitulo">Movimento</h2>
        <Escolha
          titulo="Animações"
          nome="movimento"
          valor={p.movimento}
          onMudar={(movimento) => mudar({ movimento })}
          opcoes={[
            { valor: "automatico", rotulo: "Normais" },
            { valor: "reduzido", rotulo: "Reduzidas" },
          ]}
          ajuda={
            p.movimento === "reduzido"
              ? "Telas trocam sem deslizar e nada pulsa."
              : "Se o sistema pede menos movimento, o app já reduz sozinho."
          }
        />
        <Escolha
          titulo="Vibração ao tocar"
          nome="vibracao"
          valor={p.vibracao}
          onMudar={(vibracao) => mudar({ vibracao })}
          opcoes={[
            { valor: true, rotulo: "Ligada" },
            { valor: false, rotulo: "Desligada" },
          ]}
          ajuda="Só em celulares que vibram."
        />
      </section>

      <section className="app-secao app-grupo">
        <h2 className="app-subtitulo">Paciente pela IA</h2>
        <Escolha
          titulo="Voz do paciente"
          nome="vozPaciente"
          valor={p.vozPaciente}
          onMudar={(vozPaciente) => mudar({ vozPaciente })}
          opcoes={[
            { valor: true, rotulo: "Ligada" },
            { valor: false, rotulo: "Desligada" },
          ]}
          ajuda="Com a voz ligada, o paciente lê as respostas em voz alta. Elas também aparecem escritas."
        />
      </section>
    </Tela>
  );
}
