# Teste com IA de verdade

Roteiro para a primeira gravação real, com Whisper e o modelo de correção ligados.

## 1. Configuração

No `backend/.env` (ou como variáveis de ambiente, que valem por cima do `.env`):

```
LLM_PROVEDOR=anthropic
ANTHROPIC_API_KEY=<chave da Anthropic>
TRANSCRICAO=api
OPENAI_API_KEY=<chave da OpenAI, só para o whisper-1>
```

E instale o extra da API de transcrição: `uv pip install -e ".[api]"`.

Sem chave da OpenAI dá para usar `TRANSCRICAO=local` (faster-whisper na máquina, extra
`.[local]`). O modelo é baixado do Hugging Face na primeira gravação.

## 2. Gravação

- Dois colegas, um como médico e outro como paciente, num lugar calmo.
- Caso sugerido: cartão `cefaleia-1` (mulher, 29 anos, dor de cabeça forte desde ontem à
  tarde, lateja de um lado só, a luz incomoda, já teve crises parecidas). O paciente lê o
  cartão e improvisa o resto; o médico não lê.
- Entrevista normal, de 5 a 10 minutos. Vale esquecer algumas perguntas de propósito para
  ver se a correção aponta o que faltou.
- Gravar no próprio app ou no gravador de voz do celular (m4a, mp3, wav, ogg ou webm).

## 3. Rodar

Pelo app, como o aluno faria, ou pelo script, que faz o mesmo caminho e mede o tempo:

```
cd backend
uv run python scripts/teste_real.py gravacao.m4a --hipoteses "Enxaqueca" "Cefaleia tensional"
```

O script salva a sessão completa em `resultado-teste-real.json` (fora do git).

## 4. O que conferir

| Etapa | Pergunta |
|---|---|
| Transcrição | O texto bate com o que foi dito? Termos médicos saíram certos? |
| Falas | Médico e paciente ficaram separados certo? |
| Queixa | A queixa detectada foi `cefaleia`, com um trecho que faz sentido? |
| Correção | Cada item "feito" cita uma fala que realmente prova o item? Algum "faltou" foi perguntado? |
| Notas | As duas notas parecem justas para a entrevista? |
| Tempo | Quanto levou cada etapa? (meta do plano: resultado em poucos minutos) |
| Erros | Alguma mensagem de erro ou recusa do modelo? |

Anote o que estiver errado com o trecho da transcrição; isso vira ajuste de prompt ou de
checklist.
