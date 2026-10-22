# Material-base das sprints

Fontes localizadas em `C:\Users\1144009832\Downloads`. Os dois PPTX são compostos por imagens: os slides foram extraídos do pacote e lidos visualmente. O TXT foi lido como código UTF-8.

| Arquivo lido | SHA-256 dos bytes em Downloads |
| --- | --- |
| `TestingStudio_Web_Kickoff.pptx` | `1249bb3dec0663152e25ec550c1bc083ae536f595d65418fc5cd94d32a967c35` |
| `Aula_teste_I_16092026.pptx` | `c88a087b570ef399fecd6f8c2a6936f1b6ac8294743ffe9507e2001658d7902a` |
| `cad0001_item_calculo.txt` | `ce12d94b9666f87e23fadd5218705e4c0146616f5eb831e6bf832bb3cd42f070` |

O TXT do repositório tem o mesmo conteúdo textual do arquivo em Downloads. As quebras de linha diferem: Downloads usa LF (6.441 bytes); o repositório usa CRLF (6.645 bytes, SHA-256 `1ecf8cc7ffd7db3c19982eb2888996f510b389006266eb8aa08819ba37fcb267`). O hash de uma análise identifica o texto efetivamente fornecido à aplicação.

## Requisitos encontrados nos slides

| Fonte | Local | Evidência |
| --- | --- | --- |
| Kickoff | slide 2 | Auditor/analisador web funcional com Python, Streamlit e Gemini API. |
| Kickoff | slides 4 e 6 | Módulo de caixa branca: mapear visualmente o GFC e extrair automaticamente a complexidade ciclomática de McCabe, `V(G) = E − N + 2`. |
| Kickoff | slides 4 e 7 | Módulo de fluxo de dados: rastrear pares Def-Uso; implementar mutação com falhas intencionais e cálculo do escore de mutação. |
| Kickoff | slide 8 | Detalha somente a sprint 1, já concluída segundo o usuário. |
| Aula 16/09 | slides 9 e 10 | GFC com nós/arestas e caminhos linearmente independentes. |
| Aula 16/09 | slides 11 e 12 | Todos-nós: executar cada bloco pelo menos uma vez. Todas-arestas: percorrer todos os desvios; subsume todos-nós no GFC considerado. |

A revisão dos PDFs pela equipe também identificou fundamentos complementares:

| Fonte | Páginas | Conteúdo identificado |
| --- | --- | --- |
| `Aula_Teste_I_28092026.pdf` | 3–8 | Três formas de calcular a complexidade ciclomática. |
| `Aula_Teste_I_30092026.pdf` | 4, 6–8 | Definições, usos computacionais e predicativos; caminhos Def-Uso sem redefinição; tabela por variável e critérios de fluxo de dados. |
| `Aula_Teste_I_30092026.pdf` | 12 e 15 | Operadores AOR/ROR/COR/LVR; escore `MS = Md / (Mt − Me) × 100`. |
| `Aula_Teste_I_14102026.pdf` | 5–6 | Matriz de rastreabilidade de requisitos (RTM) bidirecional. |

## Referência do legado

O CAD0001 usa Informix-4GL/Logix. Sua função de cálculo substitui cada parâmetro `NULL` por zero e calcula `(p_val1 * p_val2) + p_val3`. Os campos são `DECIMAL(12,2)`. Inclusão e alteração recalculam o valor e mantêm duas tabelas em relação 1:1; erros SQL causam rollback, e sucesso causa commit. A exclusão remove primeiro a tabela dependente.

Essa descrição caracteriza o código fornecido. Ela não resolve divergências com um oráculo de requisitos: por exemplo, rejeitar negativos ou preservar `NULL` seria uma regra diferente e exige decisão explícita.

## Sprint 4: ausência do enunciado e base externa autorizada

O Kickoff e o PPTX da aula não detalham sprint 4, pitch, duração de apresentação, roteiro ou critérios de validação da entrega. A revisão dos PDFs disponíveis também não localizou uma orientação específica para essa sprint. Os novos PDFs `Aula_Teste_I_19102026_Revisao_Avaliacao.pdf` e `Revisao_prova_I_02092026.pdf`, ambos com 15 páginas, são revisões de prova. O primeiro trata de V&V nas páginas 4–5 e aceitação na página 13; o segundo trata de V&V na página 3. São fundamentos gerais, sem rubrica de pitch ou sprint 4.

Depois dessa busca, o usuário autorizou pesquisar referências externas e implementar pitch e validação. A sprint 4 passa a usar um escopo proposto pelo projeto, explicitamente separado de exigências do professor. O roteiro de quatro minutos, os critérios e a matriz de aceitação são escolhas dessa implementação; a aceitação humana permanece pendente até avaliação registrada.

| Fonte externa consultada em 19/10/2026 | Aplicação nesta entrega |
| --- | --- |
| [Sebrae RN — Pitch](https://blog.rn.sebrae.com.br/pitch/) | Estrutura da apresentação e referência para a duração proposta. |
| [NASA — Product Validation](https://www.nasa.gov/reference/5-4-product-validation/) | Validação relacionada ao uso pretendido e às expectativas das pessoas. |
| [NASA — Verification and Validation Plan Outline](https://www.nasa.gov/reference/appendix-i-verification-and-validation-plan-outline/) | Plano, métodos e rastreabilidade das evidências. |

Consulte [sprint-4.md](sprint-4.md) para o plano e [pitch-testingstudio.md](pitch-testingstudio.md) para a fala e a demonstração propostas. As verificações técnicas em [sprints-2-3.md](sprints-2-3.md) continuam servindo para conferir os módulos anteriores; não são uma homologação acadêmica ou uma validação com usuários.
