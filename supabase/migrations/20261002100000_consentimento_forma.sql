-- Termo só de quem abriu a sessão: o colega não aceita no app. O dono aceita um termo em que
-- se compromete a avisar o colega antes de gravar, e a sessão registra esse aviso.
alter table public.consentimentos
  add column forma text not null default 'aceite'
    check (forma in ('aceite', 'declarado_pelo_dono'));

comment on column public.consentimentos.forma is
  'aceite: a pessoa aceitou o termo. declarado_pelo_dono: quem abriu a sessão declarou ter avisado o colega, como o termo dele exige.';
