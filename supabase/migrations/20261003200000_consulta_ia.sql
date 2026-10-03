-- Paciente pela IA: exame físico guiado, notas do guia e a etapa da consulta (anamnese,
-- exame físico ou despedida). Fica numa coluna só, em jsonb.
alter table public.sessoes add column consulta_ia jsonb;

comment on column public.sessoes.consulta_ia is
  'Etapa da consulta com o paciente pela IA, partes do exame físico pedidas com os achados e notas do guia. Caso fictício.';
