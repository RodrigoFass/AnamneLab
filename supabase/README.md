# Supabase

Banco (Postgres) e login com e-mail e senha (Auth) do AnamneLab. O esquema está em
`migrations/`, um arquivo por mudança, em ordem de data.

## Criar o projeto

1. No painel do Supabase, crie um projeto novo na região **South America (São Paulo)**,
   `sa-east-1`. Os dados dos alunos ficam no Brasil.
2. Em Authentication > Sign In / Providers > Email, deixe o e-mail ligado e desligue
   **Confirm email**: o envio de e-mail grátis do Supabase é muito limitado, e a conta
   nova entra direto. Em Authentication > URL Configuration, ponha o endereço do
   frontend em Site URL e em Redirect URLs (o link de "esqueci a senha" volta para ele).
3. Em Project Settings > API Keys, copie:
   - a URL do projeto: `SUPABASE_URL` no backend e `VITE_SUPABASE_URL` no frontend;
   - a chave pública (`anon` ou `publishable`): `VITE_SUPABASE_ANON_KEY` no frontend;
   - a chave secreta (`service_role` ou `secret`): `SUPABASE_SERVICE_KEY` só no
     `backend/.env`. Ela ignora RLS; nunca vai para o frontend nem para o git.

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
