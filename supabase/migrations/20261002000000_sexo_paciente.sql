-- Sexo do paciente simulado: detectado na conversa e confirmado pelo aluno com a queixa.
-- Item de checklist só de um sexo (ex.: data da última menstruação) não vale para o outro.
alter table public.sessoes
  add column sexo_paciente text check (sexo_paciente in ('feminino', 'masculino'));

comment on column public.sessoes.sexo_paciente is
  'Sexo do paciente simulado (feminino, masculino) ou nulo se não se sabe. Não é dado do aluno.';
