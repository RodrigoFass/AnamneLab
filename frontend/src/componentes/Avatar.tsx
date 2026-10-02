import type { Papel } from "../api/tipos";
import { usePerfil } from "../util/perfil";
import { DesenhoAvatar, avatarExiste } from "./Avatares";

/**
 * Avatar escolhido no perfil, ou a inicial do nome num círculo: petróleo para quem faz o
 * médico, mostarda para o paciente. Sem `avatar`, usa o do perfil quando o nome é o do dono.
 */
export function Avatar({
  nome,
  papel,
  tamanho = 32,
  avatar,
}: {
  nome: string;
  papel: Papel;
  tamanho?: number;
  avatar?: string;
}) {
  const perfil = usePerfil();
  const doDono = !!nome.trim() && nome.trim() === perfil.nome.trim();
  const escolhido = avatar ?? (doDono ? perfil.avatar : "");
  if (avatarExiste(escolhido)) {
    return (
      <span className={`app-avatar app-avatar-desenho app-avatar-${papel}`} style={{ width: tamanho, height: tamanho }} aria-hidden="true">
        <DesenhoAvatar id={escolhido} />
      </span>
    );
  }
  const inicial = nome.trim().charAt(0).toUpperCase() || (papel === "medico" ? "M" : "P");
  return (
    <span
      className={`app-avatar app-avatar-${papel}`}
      style={{ width: tamanho, height: tamanho, fontSize: Math.round(tamanho * 0.42) }}
      aria-hidden="true"
    >
      <span className="app-avatar-letra">{inicial}</span>
    </span>
  );
}
