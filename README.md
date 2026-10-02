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

Dá também para treinar sozinho, com a IA no papel do paciente. O caso parte de um cartão da
biblioteca; a IA monta uma ficha fictícia, escondida até o fim, e responde só por ela. São
dois modos, e dá para trocar no meio da conversa:

- **Chat:** você escreve a pergunta ou manda em áudio; o paciente responde por escrito.
- **Voz:** conversa contínua, sem botão de gravar. O app percebe a pausa no fim da sua
  pergunta e o paciente responde falando.

No fim, a conversa vira a transcrição da sessão e passa pela mesma correção.

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
  app/pipeline/     transcrever, rotular falas, queixa, anamnese, corrigir, sugestões,
                    paciente pela IA e voz do paciente
  app/llm/          um cliente por provedor, mesma interface (anthropic, gemini, falso)
  app/schemas/      modelos Pydantic (saída do LLM, sessão, avaliação)
  app/repositorio/  armazenamento (memória, arquivo ou Supabase)
  tests/
  scripts/          teste_real.py (teste de ponta a ponta, ver docs/teste-real.md)
frontend/           PWA em React + Vite
content/            conteúdo versionado
  schema/           JSON Schema dos checklists, cartões e queixas
  queixas.json      biblioteca fechada de queixas
  checklists/       geral.json + um por queixa (dor-toracica.json, cefaleia.json, ...)
  cartoes/          cartões de caso
  termo-gravacao.json
scripts/            validar_conteudo.py e os testes dele
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
  melhorar os produtos dele e ter pessoas revisando; o termo avisa disso. Para conferir a
  chave e os modelos, rode `uv run python -m app.testar_ia` dentro de `backend/` (no Windows
  sem uv: `.venv\Scripts\python -m app.testar_ia`); `--modelos` lista os modelos da chave.
- **Teste real de ponta a ponta:** roteiro e script em [docs/teste-real.md](docs/teste-real.md).
- **Whisper local:** `uv pip install -e ".[local]"` e `TRANSCRICAO=local`. O tamanho do
  modelo vem de `WHISPER_MODELO_LOCAL` (padrão `small`). No Windows com placa NVIDIA, o
  Whisper usa a placa e precisa de `nvidia-cublas-cu12` e `nvidia-cudnn-cu12` (cuDNN 9) com
  as pastas `bin` deles no `PATH`.
- **Whisper pela API:** `uv pip install -e ".[api]"`, `TRANSCRICAO=api` e `OPENAI_API_KEY`.
- **Voz do paciente pela IA:** sem nada, o navegador lê as respostas com uma voz em
  português do aparelho (no Windows, instale em Configurações, Hora e idioma, Fala). Voz mais
  natural, grátis, de homem e de mulher: `uv pip install -e ".[voz]"` e `VOZ_PACIENTE=edge`
  (vozes neurais do Edge; precisa de internet). Sem internet: baixe as vozes do
  Piper em português (o `.onnx` e o `.onnx.json`) para `backend/vozes/` (fora do git) e ponha
  `VOZ_PACIENTE=piper` e `PIPER_VOZ_MASCULINA` e `PIPER_VOZ_FEMININA` no `.env`. A pergunta
  falada usa a mesma transcrição da gravação (`TRANSCRICAO`).
- **Histórico no computador, sem Supabase:** `BANCO=arquivo` guarda as sessões em
  `backend/dados/historico.json` (fora do git) e o histórico continua depois de fechar o app.
  Bom para o protótipo e para uma demonstração. Excluir uma sessão no app tira ela do arquivo.
- **Supabase:** crie o projeto e aplique as migrações seguindo
  [supabase/README.md](supabase/README.md). Depois
  `uv pip install -e ".[supabase]"`, `BANCO=supabase`, `AUTH=supabase`, `SUPABASE_URL` e
  `SUPABASE_SERVICE_KEY` no backend, e `VITE_SUPABASE_URL` e `VITE_SUPABASE_ANON_KEY` no
  frontend.

### Abrir no celular

O microfone do navegador só funciona em `https` ou em `localhost`. Para abrir o app do
computador no celular, use um túnel grátis da Cloudflare: baixe o `cloudflared` em
https://github.com/cloudflare/cloudflared/releases e, com o app rodando, rode
`cloudflared tunnel --url http://localhost:5173`. Ele mostra um link
`https://....trycloudflare.com` (o Vite já aceita esse domínio). Com o Supabase ligado, ponha
o link em Site URL e em Redirect URLs (Authentication > URL Configuration). O link muda a cada
vez que o túnel abre, e o computador precisa ficar ligado. Quem tiver o link vê a tela de
entrada e pode criar conta: mande só para quem você quiser.

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
| `VOZ_PACIENTE` | `navegador`, `edge`, `piper` | `navegador` |
| `EDGE_VOZ_FEMININA`, `EDGE_VOZ_MASCULINA` | vozes do Edge | `pt-BR-FranciscaNeural`, `pt-BR-AntonioNeural` |
| `PIPER_VOZ_MASCULINA`, `PIPER_VOZ_FEMININA` | arquivos `.onnx` das vozes do Piper | |
| `BANCO` | `memoria`, `arquivo`, `supabase` | `memoria` |
| `ARQUIVO_HISTORICO` | onde `BANCO=arquivo` guarda as sessões | `dados/historico.json` |
| `AUTH` | `dev`, `supabase` | `dev` |
| `SUPABASE_URL` | URL do projeto | |
| `SUPABASE_SERVICE_KEY` | chave service_role (só no backend) | |
| `CONTAR_RASCUNHO` | `true`, `false` | `true` |
| `CORRECAO_ITENS_POR_PEDIDO` | máximo de itens por pedido de correção ao LLM, `0` para o checklist inteiro | `0` |
| `PASTA_CONTEUDO` | pasta do conteúdo | `../content` |
| `CORS_ORIGENS` | origens separadas por vírgula | `http://localhost:5173` |
| `DURACAO_MAXIMA_MIN` | duração máxima de uma gravação, em minutos | `20` |
| `TAMANHO_MAXIMO_MB` | tamanho máximo do áudio, em MB | `25` |

Frontend (`frontend/.env.local`, modelo em `frontend/.env.example`):

| Variável | O que é |
| --- | --- |
| `VITE_SUPABASE_URL` | URL do projeto; vazia usa o modo sem login (backend com `AUTH=dev`) |
| `VITE_SUPABASE_ANON_KEY` | chave pública `anon`; nunca a service_role |
| `VITE_API_URL` | endereço da API; vazio usa o proxy do Vite |

## Comandos

```
cd backend && uv run uvicorn app.main:app --reload
cd backend && uv run pytest
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

- Só quem abriu a sessão aceita o termo, uma vez; o termo traz o compromisso de avisar o colega antes de cada gravação. Nenhuma gravação começa sem o aceite do dono e o registro desse aviso na sessão, com papel, nome, versão do termo e data e hora.
- No paciente pela IA não há colega: a pergunta falada só é aceita depois do aceite do dono. A ficha fictícia que a IA montou fica na sessão.
- O áudio é apagado logo após a transcrição, inclusive quando ela falha (vale também para cada pergunta falada ao paciente pela IA); só texto e nota ficam salvos.
- Áudio, transcrição e dados pessoais nunca vão para log; segredos ficam só em `.env`, fora do git.
- O aluno pode excluir uma sessão, e isso apaga transcrição, avaliações e consentimentos.

## Licença

Repositório privado. Todos os direitos reservados; veja `LICENSE`.
