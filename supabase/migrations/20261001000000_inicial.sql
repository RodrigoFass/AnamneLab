-- AnamneLab: esquema inicial (Postgres do Supabase, região São Paulo).
--
-- Regras de privacidade (LGPD) que este esquema garante:
-- * Nenhuma tabela guarda áudio. O áudio fica só numa pasta temporária do
--   backend e é apagado logo após a transcrição, inclusive quando ela falha.
--   Aqui ficam apenas texto (transcrição) e correção.
-- * Excluir uma sessão apaga em cascata consentimentos, transcrição e
--   avaliações. Excluir a conta no Supabase Auth apaga o usuário e, em
--   cascata, todas as sessões dele.
-- * RLS ligada em todas as tabelas. O aluno autenticado só lê e apaga o que é
--   dele. Quem escreve é o backend, com a service role (que ignora RLS).
-- * fila_queixas não tem dado pessoal e não é acessível a alunos.

-- ---------------------------------------------------------------------------
-- Funções auxiliares
-- ---------------------------------------------------------------------------

create or replace function public.tocar_atualizada_em()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.atualizada_em := now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- usuarios: perfil do aluno. O id é o mesmo de auth.users.
-- ---------------------------------------------------------------------------

create table public.usuarios (
  id                uuid primary key references auth.users (id) on delete cascade,
  nome              text check (char_length(nome) between 1 and 120),  -- o backend cria a linha só com o id
  periodo           smallint check (periodo between 1 and 12),
  termos_versao     text,
  termos_aceitos_em timestamptz,
  criado_em         timestamptz not null default now()
);

comment on table public.usuarios is
  'Perfil do aluno (só estudantes de Medicina). Apagar a conta em auth.users apaga o perfil e, em cascata, as sessões.';

-- ---------------------------------------------------------------------------
-- sessoes: uma consulta simulada. O dono é quem fez o médico.
-- Não guarda o texto do caso nem áudio: só a correção e o estado.
-- ---------------------------------------------------------------------------

create table public.sessoes (
  id                   uuid primary key default gen_random_uuid(),
  dono_id              uuid not null references public.usuarios (id) on delete cascade,
  criada_em            timestamptz not null default now(),
  status               text not null default 'criada' check (status in (
                         'criada',
                         'processando_audio',
                         'aguardando_queixa',
                         'corrigindo',
                         'aguardando_hipoteses',
                         'gerando_sugestoes',
                         'concluida',
                         'erro'
                       )),
  progresso            smallint not null default 0 check (progresso between 0 and 100),
  mensagem_erro        text,
  origem_caso          text not null check (origem_caso in ('livro', 'internet', 'inventado', 'cartao')),
  cartao_id            text,
  queixa_detectada     jsonb not null default '[]'::jsonb,
  queixa_trecho        text,
  queixas_confirmadas  jsonb not null default '[]'::jsonb,
  descricao_outra      text,
  checklists_usados    jsonb not null default '[]'::jsonb,
  anamnese             jsonb,
  hipoteses_aluno      jsonb not null default '[]'::jsonb,
  notas                jsonb,
  sugestoes            jsonb
);

comment on table public.sessoes is
  'Sessão de treino. Nunca guarda áudio nem o texto do caso. Apagar a sessão apaga em cascata consentimentos, transcrição e avaliações.';
comment on column public.sessoes.checklists_usados is
  'Id, versão e status de cada checklist usado na correção, para a nota ser reprodutível.';

create index sessoes_dono_criada_idx on public.sessoes (dono_id, criada_em desc);
create index sessoes_status_idx on public.sessoes (status)
  where status not in ('concluida', 'erro');

-- ---------------------------------------------------------------------------
-- consentimentos: aceite de cada voz antes da gravação.
-- ---------------------------------------------------------------------------

create table public.consentimentos (
  id              uuid primary key default gen_random_uuid(),
  sessao_id       uuid not null references public.sessoes (id) on delete cascade,
  papel           text not null check (papel in ('medico', 'paciente')),
  nome_informado  text not null check (char_length(nome_informado) between 1 and 120),
  versao_termo    text not null,
  aceito_em       timestamptz not null default now()
);

comment on table public.consentimentos is
  'Nenhuma gravação começa sem o aceite das duas vozes. Apagado em cascata com a sessão.';

create index consentimentos_sessao_idx on public.consentimentos (sessao_id);

-- ---------------------------------------------------------------------------
-- transcricoes: só texto. O áudio que a originou já foi apagado.
-- ---------------------------------------------------------------------------

create table public.transcricoes (
  id          uuid primary key default gen_random_uuid(),
  sessao_id   uuid not null unique references public.sessoes (id) on delete cascade,
  falas       jsonb not null default '[]'::jsonb,
  editada     boolean not null default false,
  editada_em  timestamptz,
  criada_em   timestamptz not null default now()
);

comment on table public.transcricoes is
  'Falas rotuladas (médico ou paciente). O áudio nunca é guardado: é apagado logo após a transcrição. Apagada em cascata com a sessão.';

-- ---------------------------------------------------------------------------
-- avaliacoes: um item de checklist corrigido.
-- ---------------------------------------------------------------------------

create table public.avaliacoes (
  id                uuid primary key default gen_random_uuid(),
  sessao_id         uuid not null references public.sessoes (id) on delete cascade,
  ordem             integer not null default 0,
  item_id           text not null,
  checklist_id      text not null,
  checklist_versao  integer not null check (checklist_versao >= 1),
  secao             text not null,
  texto             text not null,
  status            text not null check (status in ('feito', 'faltou')),
  trecho            text,
  mensagem          text not null,
  peso              smallint not null check (peso >= 1),
  conta_na_nota     boolean not null,
  contestacao       jsonb,
  constraint avaliacoes_sessao_item_unico unique (sessao_id, item_id),
  -- Regra do produto: item feito sempre cita um trecho da transcrição.
  constraint avaliacoes_feito_com_trecho check (status <> 'feito' or trecho is not null)
);

comment on table public.avaliacoes is
  'Correção item a item. Apagada em cascata com a sessão.';

create index avaliacoes_checklist_idx on public.avaliacoes (checklist_id, checklist_versao);

-- ---------------------------------------------------------------------------
-- fila_queixas: queixas "outra" que ainda não estão na biblioteca.
-- Sem vínculo com aluno ou sessão: só a descrição normalizada e a contagem.
-- ---------------------------------------------------------------------------

create table public.fila_queixas (
  id                      uuid primary key default gen_random_uuid(),
  descricao_normalizada   text not null unique,
  exemplo                 text not null,
  frequencia              integer not null default 1 check (frequencia >= 1),
  status                  text not null default 'pendente'
                            check (status in ('pendente', 'em_revisao', 'incluida')),
  criada_em               timestamptz not null default now(),
  atualizada_em           timestamptz not null default now()
);

comment on table public.fila_queixas is
  'Queixas fora da biblioteca, para revisão. Sem dado pessoal; acesso só pela service role.';

create index fila_queixas_status_idx on public.fila_queixas (status, frequencia desc);

create trigger fila_queixas_atualizada_em
  before update on public.fila_queixas
  for each row execute function public.tocar_atualizada_em();

-- ---------------------------------------------------------------------------
-- Permissões
-- O papel anon não acessa nada. O papel authenticated só lê e apaga.
-- Escritas passam pelo backend, com a service role.
-- ---------------------------------------------------------------------------

revoke all on table
  public.usuarios, public.sessoes, public.consentimentos,
  public.transcricoes, public.avaliacoes, public.fila_queixas
from anon, authenticated;

grant select on table public.usuarios to authenticated;
grant select, delete on table
  public.sessoes, public.consentimentos, public.transcricoes, public.avaliacoes
to authenticated;

grant all on table
  public.usuarios, public.sessoes, public.consentimentos,
  public.transcricoes, public.avaliacoes, public.fila_queixas
to service_role;

revoke all on function public.tocar_atualizada_em() from public, anon, authenticated;

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

alter table public.usuarios       enable row level security;
alter table public.sessoes        enable row level security;
alter table public.consentimentos enable row level security;
alter table public.transcricoes   enable row level security;
alter table public.avaliacoes     enable row level security;
alter table public.fila_queixas   enable row level security;

-- usuarios: o aluno vê o próprio perfil.
create policy usuarios_ler_proprio on public.usuarios
  for select to authenticated
  using (id = (select auth.uid()));

-- sessoes: o aluno vê e apaga as próprias sessões.
create policy sessoes_ler_proprias on public.sessoes
  for select to authenticated
  using (dono_id = (select auth.uid()));

create policy sessoes_apagar_proprias on public.sessoes
  for delete to authenticated
  using (dono_id = (select auth.uid()));

-- Tabelas filhas: acesso pelo dono da sessão.
create policy consentimentos_ler_proprios on public.consentimentos
  for select to authenticated
  using (exists (
    select 1 from public.sessoes s
    where s.id = consentimentos.sessao_id and s.dono_id = (select auth.uid())
  ));

create policy consentimentos_apagar_proprios on public.consentimentos
  for delete to authenticated
  using (exists (
    select 1 from public.sessoes s
    where s.id = consentimentos.sessao_id and s.dono_id = (select auth.uid())
  ));

create policy transcricoes_ler_proprias on public.transcricoes
  for select to authenticated
  using (exists (
    select 1 from public.sessoes s
    where s.id = transcricoes.sessao_id and s.dono_id = (select auth.uid())
  ));

create policy transcricoes_apagar_proprias on public.transcricoes
  for delete to authenticated
  using (exists (
    select 1 from public.sessoes s
    where s.id = transcricoes.sessao_id and s.dono_id = (select auth.uid())
  ));

create policy avaliacoes_ler_proprias on public.avaliacoes
  for select to authenticated
  using (exists (
    select 1 from public.sessoes s
    where s.id = avaliacoes.sessao_id and s.dono_id = (select auth.uid())
  ));

create policy avaliacoes_apagar_proprias on public.avaliacoes
  for delete to authenticated
  using (exists (
    select 1 from public.sessoes s
    where s.id = avaliacoes.sessao_id and s.dono_id = (select auth.uid())
  ));

-- fila_queixas: RLS ligada e nenhuma política. Só a service role acessa.
