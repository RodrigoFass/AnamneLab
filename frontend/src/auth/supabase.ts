import type { SupabaseClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const chave = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

/** Login só existe quando as duas variáveis estão preenchidas. Sem elas, modo dev. */
export const loginAtivo = Boolean(url && chave);

let cliente: Promise<SupabaseClient> | null = null;

/** Carrega o Supabase só quando o login está ativo (no modo dev ele nem é baixado). */
export function supabase(): Promise<SupabaseClient> {
  if (!loginAtivo || !url || !chave) {
    return Promise.reject(new Error("Login desativado neste ambiente."));
  }
  if (!cliente) {
    cliente = import("@supabase/supabase-js").then(({ createClient }) =>
      createClient(url, chave, {
        auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
      }),
    );
  }
  return cliente;
}

/** Token de acesso atual, ou null no modo dev ou sem login. */
export async function tokenAtual(): Promise<string | null> {
  if (!loginAtivo) return null;
  const sb = await supabase();
  const { data } = await sb.auth.getSession();
  return data.session?.access_token ?? null;
}
