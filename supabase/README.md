# Supabase

Banco (Postgres) e login (Auth) do AnamneLab. O esquema está em
`migrations/20261001000000_inicial.sql`.

## Criar o projeto

1. No painel do Supabase, crie um projeto novo na região **South America (São Paulo)**,
   `sa-east-1`. Os dados dos alunos ficam no Brasil.
2. Em Authentication, ligue o login por link mágico (e-mail) e cadastre a URL do
   frontend em Redirect URLs.
3. Em Project Settings > API, copie:
   - a URL do projeto: `SUPABASE_URL` no backend e `VITE_SUPABASE_URL` no frontend;
   - a chave `anon`: `VITE_SUPABASE_ANON_KEY` no frontend;
   - a chave `service_role`: `SUPABASE_SERVICE_KEY` só no `backend/.env`. Ela ignora
     RLS; nunca vai para o frontend nem para o git.

## Aplicar a migração

Com a CLI do Supabase:

```
supabase login
supabase link --project-ref <ref-do-projeto>
supabase db push
```

Sem a CLI: abra o SQL Editor do painel, cole o conteúdo de cada arquivo de `migrations/`,
em ordem de data, e rode uma vez cada.

## O que o esquema garante

- Nenhuma tabela guarda áudio. O áudio é apagado pelo backend logo após a transcrição.
- Apagar uma sessão apaga em cascata consentimentos, transcrição e avaliações.
  Apagar a conta em Authentication apaga o perfil e todas as sessões do aluno.
- RLS ligada em todas as tabelas. O aluno só lê e apaga o que é dele; quem grava é o
  backend, com a service role. `fila_queixas` não é acessível a alunos.
- Item `feito` sem trecho citado é recusado pelo próprio banco.

Mudou o esquema? Crie uma nova migração com data no nome
(`supabase migration new <nome>`); não edite uma migração já aplicada.
