# API do protótipo

Contrato entre `backend/` e `frontend/`. Os modelos estão em `backend/app/schemas/sessao.py`
e são espelhados em `frontend/src/api/tipos.ts`. Todas as rotas ficam sob `/api` e
respondem JSON. Erros seguem `{"detail": "<mensagem em PT-BR, tom de preceptor>"}`.

## Autenticação

- `AUTH=dev` (padrão local): o backend usa um aluno fixo de desenvolvimento; o
  frontend não pede login.
- `AUTH=supabase`: o frontend faz login pelo Supabase Auth (link mágico por e-mail) e
  manda `Authorization: Bearer <access_token>`. O backend confere o token no Supabase.

Toda rota de sessão só enxerga sessões do próprio dono (quem fez o médico).

## Rotas

| Método | Rota | Corpo | Resposta | O que faz |
| --- | --- | --- | --- | --- |
| GET | `/api/saude` | | `Saude` | Verificação simples. `{"ok": true, "modo_demonstracao": <bool>}`: `modo_demonstracao` vem `true` quando `LLM_PROVEDOR=falso` ou `TRANSCRICAO=falso`, e a interface mostra em todas as telas que a transcrição e a correção são de exemplo |
| GET | `/api/queixas` | | `Queixa[]` | Biblioteca fechada de queixas |
| GET | `/api/cartoes/sortear?queixa=<id>` | | `Cartao` | Sorteia um cartão (queixa opcional) |
| GET | `/api/termo` | | `Termo` | Termo de gravação vigente (versão e texto) |
| GET | `/api/sessoes` | | `SessaoResumo[]` | Histórico do aluno, mais recente primeiro |
| POST | `/api/sessoes` | `SessaoCriar` | `Sessao` | Abre uma sessão (status `criada`). Com `origem_caso: "paciente_ia"`, sorteia um cartão (ou usa `cartao_id`), monta a ficha do paciente e abre com status `conversando`; 503 se a IA não responder |
| GET | `/api/sessoes/{id}` | | `Sessao` | Estado atual; o frontend consulta a cada 2 s enquanto processa |
| DELETE | `/api/sessoes/{id}` | | 204 | Apaga sessão, transcrição, avaliações e consentimentos |
| POST | `/api/sessoes/{id}/consentimentos` | `ConsentimentoCriar` | `Consentimento` | Registra o aceite de quem abriu a sessão (`forma: "aceite"`, o padrão) ou o aviso ao colega (`forma: "declarado_pelo_dono"`, que exige antes o aceite do dono no outro papel; senão 409) |
| POST | `/api/sessoes/{id}/conversa` | `PerguntaPaciente` (`texto`, até 1000 caracteres) | `Sessao` | Paciente pela IA: manda uma pergunta e recebe a sessão com a pergunta e a resposta nas falas. Só com status `conversando`; 422 para pergunta vazia ou longa, 503 se a IA não responder (a pergunta não fica) |
| POST | `/api/sessoes/{id}/encerrar` | | `Sessao` | Paciente pela IA: fim da entrevista. Status vai para `aguardando_queixa` com a queixa do cartão sugerida; a ficha `caso_ia` passa a vir na sessão |
| POST | `/api/sessoes/{id}/audio` | multipart `audio` | `Sessao` | Exige um registro por papel (médico e paciente) na versão vigente do termo. Status vai para `processando_audio` e o processamento roda em segundo plano |
| PUT | `/api/sessoes/{id}/transcricao` | `TranscricaoEditar` | `Sessao` | Corrige quem disse o quê ou um erro de transcrição; marca `transcricao_editada` |
| POST | `/api/sessoes/{id}/queixa` | `QueixaConfirmar` | `Sessao` | Aluno confirma a queixa e o sexo do paciente simulado (`sexo_paciente`: `feminino`, `masculino` ou `null`; sem o campo, fica o detectado na conversa). Item de checklist só de um sexo sai da correção quando o paciente é do outro. `outra` vale sozinha (não se mistura com queixa da lista) e entra na `fila_queixas`. Dispara anamnese e correção em segundo plano |
| POST | `/api/sessoes/{id}/hipoteses` | `HipotesesAluno` | `Sessao` | Aluno escreve as hipóteses. Libera a correção e dispara as sugestões da IA |
| POST | `/api/sessoes/{id}/contestacoes` | `ContestacaoCriar` | `Sessao` | Contesta um item. O trecho precisa existir na transcrição e pegar uma fala do entrevistador (fala só do paciente não basta), e o LLM confere se ele mostra que o entrevistador investigou o item (tarefa `verificar_contestacao`, saída `TrechoCumpreItem`). Confirmado: `procedente`, o item vira feito com esse trecho e a nota é recalculada. Sem trecho, trecho que não existe ou só do paciente, LLM que nega ou que falha: `pendente_professor` e a nota não muda |

## Ciclo da sessão

```
criada
  └─ POST audio ──────────────► processando_audio  (transcrever, apagar áudio, rotular falas, detectar queixa)
                                   └──────────────► aguardando_queixa
conversando (paciente pela IA)
  └─ POST conversa (repete) ─► conversando
  └─ POST encerrar ──────────► aguardando_queixa
  POST queixa ─────────────────► corrigindo        (anamnese, correção, conferência dos trechos, notas)
                                   └──────────────► aguardando_hipoteses
  POST hipoteses ──────────────► gerando_sugestoes (hipóteses sugeridas; perguntas sugeridas só se falta checklist)
                                   └──────────────► concluida
qualquer etapa com falha ───────► erro (mensagem_erro em PT-BR)
```

- O áudio é apagado logo depois da transcrição, inclusive quando ela falha.
- `avaliacoes` e `notas` só aparecem na resposta a partir de `gerando_sugestoes`: o aluno
  escreve as hipóteses antes de ver a correção.
- Enquanto `aguardando_queixa`, o aluno pode editar a transcrição.
- Paciente pela IA: `caso_ia` vem `null` enquanto `conversando` (é o gabarito do caso) e aparece depois de encerrar.
- Duração máxima do áudio: 20 minutos; tamanho máximo: 25 MB.

## Sugestões da IA

- `sugestoes.hipoteses`: hipóteses para estudo, sempre "sugestão, não gabarito".
- `sugestoes.perguntas_sugeridas`: terceira camada da correção, fora da nota. Só vem
  preenchida quando alguma queixa confirmada é `outra` ou não tem checklist; nos outros
  casos o backend devolve `[]`, mesmo que o LLM mande perguntas. A interface só mostra a
  seção quando há alguma.

## Notas

- Duas notas de 0 a 100: `geral` (checklist geral) e `queixa` (checklists das queixas
  confirmadas). Nota = soma dos pesos feitos / soma dos pesos, arredondada.
- Item com o mesmo id em dois checklists conta uma vez só.
- Só checklist `aprovado` conta. Com `CONTAR_RASCUNHO=true` (padrão do protótipo enquanto
  nenhum checklist foi assinado), rascunho também conta e `notas.provisoria` vem `true`;
  a interface avisa que a nota é provisória.
