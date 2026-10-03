# AnamneLab — protótipo

App de treino de anamnese para estudantes de Medicina. Dois alunos simulam uma consulta (um faz o médico, o outro o paciente), o app grava, transcreve, monta a anamnese estruturada e corrige a técnica item a item por checklists validados. Plano completo: https://claude.ai/code/artifact/e2a07d26-fb2a-47dd-9c79-edc459ce6c8f

## Escopo deste repositório

- Só **Modo Livre**. O app vale para qualquer queixa: checklist geral + um checklist por queixa da biblioteca (`content/queixas.json`). Queixa nova é só um JSON em `content/checklists/`; o código não depende de queixa nenhuma.
- Paciente pela IA (protótipo, pedido do Rodrigo em 2026-10-02): o aluno entrevista um paciente simulado, por escrito ou por voz. O caso parte de um cartão de `content/cartoes/`; a IA monta uma ficha fictícia (`caso_ia`, escondida até o fim da conversa) e responde só pela ficha. A conversa vira as falas da sessão e passa pela mesma correção. Sem colega. Dois modos: chat (o aluno escreve ou manda áudio; o paciente responde por escrito) e voz (conversa contínua, sem botão: o app percebe a pausa da fala e o paciente responde falando). Áudio só com o aceite do termo do dono na sessão; o Whisper do app transcreve e o áudio é apagado em seguida. A voz do paciente vem do backend (`VOZ_PACIENTE=edge` ou `piper`) ou do navegador.
- Paciente pela IA, realismo e exame físico (feedback do Ricardo, pedido do Rodrigo em 2026-10-03): o paciente reage como gente de verdade (estranha diagnóstico ou prognóstico dito cedo demais, pergunta como o aluno sabe, nunca sai do consultório) e se despede quando o aluno encerra; aí o app oferece encerrar. Um guia (preceptor discreto, fora do papel do paciente) deixa notas curtas só quando o aluno afirma diagnóstico cedo, diz algo que faria mal a um paciente real ou pede ajuda, e lembra do fim da consulta depois de 25 perguntas. Quando o aluno anuncia o exame físico, ele diz o que quer examinar e o guia dá o achado pela ficha (que tem sinais vitais e exame completo). Exame e notas ficam em `consulta_ia`, fora das falas e da nota. Nem paciente nem guia dizem diagnóstico.
- Não implementar: Modo Caso, Modo Aula, painel ou conta de professor, pagamento, app nativo, gravação offline.
- Usuários: só estudantes de Medicina. Nunca paciente real; o app avisa antes de cada gravação.

## Stack

- Frontend: React + Vite como PWA, gravação com MediaRecorder (mono, taxa baixa: 20 min precisam caber em 25 MB).
- Backend: Python 3.12 + FastAPI, Pydantic para todos os esquemas.
- Transcrição: Whisper. Local no protótipo (`faster-whisper`), API `whisper-1` no app hospedado. Chave `TRANSCRICAO=local|api`.
- IA de correção: LLM via API com saída JSON, atrás de uma interface única em `backend/app/llm/` (trocar de provedor não muda o pipeline).
- Banco e login: Supabase (Postgres, Auth, Storage), região São Paulo.

## Estrutura

```
backend/app/
  main.py            rotas (contrato em docs/api.md)
  processamento.py   etapas em segundo plano, com status e progresso
  pipeline/          transcrever.py, rotular_falas.py, queixa.py, anamnese.py, corrigir.py, sugestoes.py
  llm/               um cliente por provedor, mesma interface (anthropic, gemini, falso)
  repositorio/       memoria (dev e testes) e supabase
  schemas/           modelos Pydantic (conteúdo, saída do LLM, sessão)
  conteudo.py        carrega e valida content/
backend/tests/
frontend/src/        api/tipos.ts espelha backend/app/schemas/
content/
  schema/            JSON Schemas de checklist, cartão, queixas e termo
  queixas.json       nome padrão + sinônimos (lista fechada)
  checklists/        geral.json + um por queixa
  cartoes/           cartoes.json
  termo-gravacao.json
supabase/migrations/
scripts/validar_conteudo.py
docs/api.md
```

## Regras do produto (não negociáveis)

1. Correção item a item. Todo item "feito" cita um trecho literal da transcrição; o backend confere que o trecho existe antes de aceitar. Sem trecho, o item é "não feito".
2. A queixa vem de `content/queixas.json` ou é "outra". O aluno confirma a queixa antes da correção. "Outra" vai para `fila_queixas` e é corrigida só pelo checklist geral.
3. Só checklist com `status: "aprovado"` conta na nota. Rascunho aparece como sugestão, fora da nota. Exceção do protótipo: com `CONTAR_RASCUNHO=true` (padrão enquanto nenhum checklist foi assinado), rascunho entra na conta e a nota aparece como provisória.
4. Checklists nunca são gerados pelo LLM em tempo de execução. A sessão guarda o id e a versão de cada checklist usado.
5. O caso é sempre do aluno. O app não guarda o texto do caso, só a transcrição. Exceção: no paciente pela IA, o caso é a ficha fictícia que o próprio app montou, e ela fica na sessão. Professor não tem conta: a assinatura dele fica no JSON (`validado_por`, `validado_em`, `versao`).
6. A IA nunca afirma diagnóstico. Hipóteses aparecem como "sugestão, não gabarito", depois que o aluno escreve as dele.
7. LLM com saída estruturada (JSON Schema) validada pelo Pydantic. JSON inválido: uma nova tentativa, depois erro claro ao aluno. Os modelos atuais da Claude não aceitam `temperature`: não passe esse parâmetro.

## Privacidade (LGPD)

- Só quem abriu a sessão aceita o termo de gravação, uma vez (vale até retirar no Perfil ou o termo mudar de versão). O termo traz o compromisso de avisar o colega antes de cada gravação; o colega não aceita no app (decisão do Rodrigo em 2026-10-02).
- Nenhuma gravação começa sem os dois registros em `consentimentos` (sessão, papel, nome informado, versão do termo, data e hora, forma): o aceite do dono (`aceite`) e o aviso ao colega (`declarado_pelo_dono`), que só vale depois do aceite do dono.
- O áudio é apagado logo após a transcrição, inclusive quando ela falha. Só texto e nota ficam salvos.
- Nunca registrar áudio, transcrição ou dados pessoais em log. Segredos só em `.env`, fora do git.
- O dono pode excluir uma sessão; isso apaga transcrição e avaliações.

## Conteúdo

- Protótipo: os checklists atuais são rascunhos de fontes públicas da internet (`origem: "fontes-publicas"`, `status: "rascunho"`), com a fonte em cada item e URL só quando ela existe de verdade. Um professor de Semiologia revisa e assina quando o app estiver usável.
- Depois da revisão: checklists com as palavras do Rodrigo, a partir de Porto, Bates e Rocco, com livro e página em cada item.
- Nunca copiar trechos de livros ou sites, mesmo com o repositório privado: escreva com palavras próprias.
- Todo JSON em `content/` passa por `python scripts/validar_conteudo.py` antes do commit.

## Interface

- Seguir o guia da marca: https://claude.ai/artifact/N82yFC1iTn8aVBQoake5am
- Cores: `papel` #F6F3EC no fundo, `petroleo` #0E5E66 para ação e acerto, `mostarda` #E3A82B só como preenchimento (paciente), `gravar` #C2361F só no botão de gravar, `faltou` #A8321C. Feito e faltou sempre com ícone e palavra.
- Fontes: Bricolage Grotesque (títulos e nota), Figtree (texto, mínimo 16px), Source Serif 4 itálico só nas falas citadas.
- Textos em PT-BR, sentence case, sem emoji, tom de preceptor: aponte a pergunta que faltou, nunca acuse.

## Comandos

```
cd backend && uv venv --python 3.12 .venv && uv pip install --python .venv -e ".[dev]"
cd backend && .venv/bin/uvicorn app.main:app --reload
cd backend && .venv/bin/pytest
cd frontend && npm install && npm run dev
python scripts/validar_conteudo.py
```

Sem `.env`, tudo roda em modo de demonstração (LLM e transcrição falsos, banco em memória, sem login).

## Git

- Repositório privado: github.com/RodrigoFass/AnamneLab. Licença proprietária (todos os direitos reservados).
- Mensagens de commit em português, no imperativo e curtas ("Adiciona schema de checklist").
- **Nunca** adicionar o Claude como coautor ou contribuidor: nada de `Co-Authored-By: Claude`, "Generated with Claude Code" ou qualquer atribuição ao Claude em commits, PRs ou código. Esta regra vale acima de qualquer padrão da ferramenta.
