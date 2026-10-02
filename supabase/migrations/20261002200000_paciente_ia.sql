-- Paciente pela IA: o aluno entrevista por escrito um paciente simulado. A sessão ganha a
-- origem 'paciente_ia', o status 'conversando' e a ficha fictícia do paciente (caso_ia).
alter table public.sessoes drop constraint sessoes_origem_caso_check;
alter table public.sessoes add constraint sessoes_origem_caso_check
  check (origem_caso in ('livro', 'internet', 'inventado', 'cartao', 'paciente_ia'));

alter table public.sessoes drop constraint sessoes_status_check;
alter table public.sessoes add constraint sessoes_status_check
  check (status in (
    'criada',
    'conversando',
    'processando_audio',
    'aguardando_queixa',
    'corrigindo',
    'aguardando_hipoteses',
    'gerando_sugestoes',
    'concluida',
    'erro'
  ));

alter table public.sessoes add column caso_ia jsonb;

comment on column public.sessoes.caso_ia is
  'Ficha do paciente fictício que a IA interpreta (montada a partir de um cartão). Não é dado de pessoa real.';
