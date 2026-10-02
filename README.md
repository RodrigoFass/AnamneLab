# AnamneLab

Treino de anamnese para estudantes de Medicina. Dois colegas simulam uma consulta: um faz
o médico, o outro o paciente. O app grava a conversa, transcreve, separa quem disse o quê,
monta a anamnese estruturada e corrige a técnica item a item, como um preceptor faria ao
seu lado: aponta a pergunta que faltou e mostra, com a sua própria fala, o que você fez bem.

Nada de nota sem prova. Todo item marcado como feito cita um trecho literal da transcrição,
conferido pelo backend antes de entrar na correção. A queixa vem de uma lista fechada e é
confirmada pelo aluno, os checklists são fixos e versionados, e a IA nunca afirma
diagnóstico: as hipóteses dela aparecem como sugestão, não gabarito, depois que você
escreveu as suas.

> **Aviso: checklists provisórios.** Os checklists atuais (o geral e um para cada uma das 10
> queixas da biblioteca: dor torácica, dispneia, dor abdominal, cefaleia, febre, tosse, dor
> lombar, síncope, edema e diarreia) são um rascunho montado a partir de fontes públicas da
> internet (`status: "rascunho"`, `origem: "fontes-publicas"`) e **ainda não foram revisados
> por um professor**. Enquanto nenhum checklist estiver aprovado, o protótipo roda com
> `CONTAR_RASCUNHO=true`: o rascunho entra na conta e a nota aparece marcada como
> **provisória**. Use para treinar, não como avaliação.

## Estrutura

```
backend/            API em Python 3.12 + FastAPI
  app/main.py       rotas (contrato em docs/api.md)
  app/pipeline/     transcrever, rotular falas, queixa, anamnese, corrigir, sugestões
  app/llm/          um cliente por provedor, mesma interface (anthropic, gemini, falso)
  app/schemas/      modelos Pydantic (saída do LLM, sessão, avaliação)
  app/repositorio/  armazenamento (memória ou Supabase)
  tests/
frontend/           PWA em React + Vite
content/            conteúdo versionado
  schema/           JSON Schema dos checklists, cartões e queixas
  queixas.json      biblioteca fechada de queixas
  checklists/       geral.json + um por queixa (dor-toracica.json, cefaleia.json, ...)
  cartoes/          cartões de caso
  termo-gravacao.json
scripts/            validar_conteudo.py e testes
supabase/           migrações do Postgres e instruções de implantação
docs/api.md         contrato entre backend e frontend
```

## Rodar local

Pré-requisitos: [uv](https://docs.astral.sh/uv/) (Python 3.12) e Node 22.

### Modo 100% falso (sem chave nenhuma)

É o padrão. O LLM devolve respostas determinísticas, a transcrição devolve uma conversa de
exemplo, o banco fica em memória e o login é um aluno fixo de desenvolvimento. Serve para
mexer na interface e no pipeline sem rede e sem custo.

```
cd backend
uv venv --python 3.12
uv pip install -e ".[dev]"
cp .env.example .env
uv run uvicorn app.main:app --reload
```

Em outro terminal:

```
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Abra http://localhost:5173. O Vite encaminha `/api` para o backend em http://localhost:8000.

### Ligar os serviços de verdade

Tudo se liga no `backend/.env` (e no `frontend/.env.local` para o login):

- **IA de correção (Anthropic):** `LLM_PROVEDOR=anthropic` e `ANTHROPIC_API_KEY`. O modelo
  sai de `LLM_MODELO` e o esforço de `LLM_ESFORCO`. A saída é JSON validado pelo Pydantic;
  JSON inválido ganha uma nova tentativa e, depois, um erro claro ao aluno.
- **IA de correção grátis (Gemini):** crie uma chave no Google AI Studio
  (https://aistudio.google.com/apikey, sem cartão) e ponha `LLM_PROVEDOR=gemini` e
  `GEMINI_API_KEY`. `GEMINI_MODELOS` é a lista de modelos em ordem: quando um esgota a cota
  grátis, o app tenta o próximo (com cota por minuto e espera curta, espera e tenta o mesmo).
  As tarefas simples começam por `GEMINI_MODELOS_LEVES`, para sobrar cota dos modelos melhores
  para separar as falas e corrigir. A cota grátis dos modelos melhores é pequena: evite rodar
  muitos testes no dia de uma demonstração. No plano grátis o Google pode guardar o texto, usar para
  melhorar os produtos dele e ter pessoas revisando; o termo (v2) avisa disso. Para conferir a
  chave e os modelos, rode `uv run python -m app.testar_ia` dentro de `backend/` (no Windows
  sem uv: `.venv\Scripts\python -m app.testar_ia`); `--modelos` lista os modelos da chave.
- **Whisper local:** `uv pip install -e ".[local]"` e `TRANSCRICAO=local`. O tamanho do
  modelo vem de `WHISPER_MODELO_LOCAL` (padrão `small`). No Windows com placa NVIDIA, o
  Whisper usa a placa e precisa de `nvidia-cublas-cu12` e `nvidia-cudnn-cu12` (cuDNN 9) com
  as pastas `bin` deles no `PATH`.
- **Whisper pela API:** `uv pip install -e ".[api]"`, `TRANSCRICAO=api` e `OPENAI_API_KEY`.
- **Supabase:** crie o projeto e aplique a migração seguindo `supabase/README.md`. Depois
  `uv pip install -e ".[supabase]"`, `BANCO=supabase`, `AUTH=supabase`, `SUPABASE_URL` e
  `SUPABASE_SERVICE_KEY` no backend, e `VITE_SUPABASE_URL` e `VITE_SUPABASE_ANON_KEY` no
  frontend.

## Variáveis de ambiente

Backend (`backend/.env`, modelo em `backend/.env.example`):

| Variável | Valores | Padrão |
| --- | --- | --- |
| `LLM_PROVEDOR` | `anthropic`, `gemini`, `falso` | `falso` |
| `LLM_MODELO` | id do modelo | `claude-opus-5-5` |
| `LLM_ESFORCO` | `low`, `medium`, `high`, `xhigh`, `max` | `medium` |
| `ANTHROPIC_API_KEY` | chave da API | |
| `GEMINI_API_KEY` | chave do Google AI Studio | |
| `GEMINI_MODELOS` | modelos em ordem, separados por vírgula | `gemini-3.8-flash,gemini-3.5-flash,gemini-3.5-flash-lite` |
| `GEMINI_MODELOS_LEVES` | modelos que começam as tarefas simples (queixa, anamnese, sugestões); vazio usa `GEMINI_MODELOS` | `gemini-3.5-flash-lite` |
| `GEMINI_TEMPERATURA` | temperatura do Gemini; vazia usa o padrão do modelo (o `.env.example` sugere `0`) | vazia |
| `TRANSCRICAO` | `local`, `api`, `falso` | `falso` |
| `WHISPER_MODELO_LOCAL` | tamanho do faster-whisper | `small` |
| `OPENAI_API_KEY` | chave da API (Whisper) | |
| `BANCO` | `memoria`, `supabase` | `memoria` |
| `AUTH` | `dev`, `supabase` | `dev` |
| `SUPABASE_URL` | URL do projeto | |
| `SUPABASE_SERVICE_KEY` | chave service_role (só no backend) | |
| `CONTAR_RASCUNHO` | `true`, `false` | `true` |
| `CORRECAO_ITENS_POR_PEDIDO` | máximo de itens por pedido de correção ao LLM, `0` para o checklist inteiro | `0` |
| `CORS_ORIGENS` | origens separadas por vírgula | `http://localhost:5173` |

Frontend (`frontend/.env.local`, modelo em `frontend/.env.example`):

| Variável | O que é |
| --- | --- |
| `VITE_SUPABASE_URL` | URL do projeto; vazia usa o modo sem login (backend com `AUTH=dev`) |
| `VITE_SUPABASE_ANON_KEY` | chave pública `anon`; nunca a service_role |
| `VITE_API_URL` | endereço da API; vazio usa o proxy do Vite |

## Comandos

```
cd backend && uvicorn app.main:app --reload
cd backend && pytest
cd frontend && npm run dev
python scripts/validar_conteudo.py
```

O CI (`.github/workflows/ci.yml`) roda a validação do conteúdo, os testes do backend e o
build do frontend em todo push e pull request.

## Regras de conteúdo

- Todo JSON em `content/` passa por `python scripts/validar_conteudo.py` antes do commit.
  Arquivo que não valida não entra.
- Checklists nunca são gerados pela IA em tempo de execução. Cada sessão guarda o id e a
  versão de cada checklist usado.
- Só checklist com `status: "aprovado"`, assinado pelo professor (`validado_por`,
  `validado_em`, `versao`), conta na nota definitiva. Mudou um item, sobe a versão.
- Escreva os itens com palavras próprias, citando livro e página. Nunca copie trechos
  de livros.

## Privacidade (LGPD)

- Nenhuma gravação começa sem o consentimento das duas vozes, registrado com papel, nome, versão do termo e data e hora.
- O áudio é apagado logo após a transcrição, inclusive quando ela falha; só texto e nota ficam salvos.
- Áudio, transcrição e dados pessoais nunca vão para log; segredos ficam só em `.env`, fora do git.
- O aluno pode excluir uma sessão, e isso apaga transcrição, avaliações e consentimentos.

## Licença

Repositório privado. Todos os direitos reservados; veja `LICENSE`.
