# Pitch do TestingStudio Web

Roteiro proposto de aproximadamente **quatro minutos**, incluindo a demonstração. Foi preparado por solicitação do usuário com pesquisa externa; não corresponde a uma duração ou rubrica encontrada no material do professor. Público assumido: estudantes de teste de software e avaliador acadêmico. Ajustar após um ensaio cronometrado.

## Preparação

Abrir o aplicativo no modo **Preparação local (sem API)**, restaurar o TXT original e deixar as sprints acessíveis. Executar a suíte inicial na sprint 3 antes do ensaio e exportar as evidências. Para a apresentação, consultar os valores da execução atual. Se o fonte ou a suíte mudar, executar novamente.

Usar os seis slides disponibilizados no aplicativo, na sequência abaixo. O navegador pode ser a própria apresentação; o HTML exportado também funciona offline. O modo local permite realizar a demonstração sem depender de uma chamada ao Gemini.

| Tempo proposto | Tela | Mensagem principal |
| --- | --- | --- |
| 0:00–0:35 | O problema: transformar código em evidência de teste | Ligar requisitos, código e evidências no estudo de um legado. |
| 0:35–1:10 | Público e proposta do TestingStudio Web | Um laboratório web para acompanhar as técnicas de teste. |
| 1:10–2:00 | Demonstração em quatro passos | Observar uma regra, seu grafo, um par DU e a resposta da suíte a um mutante. |
| 2:00–2:45 | Evidências disponíveis nesta execução | Ler o relatório atual e seus identificadores. |
| 2:45–3:25 | Validação e limites do resultado | Explicar o que foi verificado e o que depende das pessoas. |
| 3:25–4:00 | Pedido e próximo passo | Convidar a avaliar o uso e decidir os próximos passos. |

## 1. O problema: transformar código em evidência de teste

> Como mostrar a relação entre uma regra de negócio, o código que a implementa e os testes que deveriam avaliá-la? Este é o desafio que usamos no TestingStudio Web. Nosso cenário é o CAD0001, um programa de cadastro em Informix-4GL. A ferramenta foi preparada como laboratório para estudantes explorarem técnicas de teste e discutirem suas evidências com o avaliador.

**Na tela:** título do projeto e nome CAD0001. Apresentar o público como hipótese de uso do projeto; não afirmar que já houve adoção ou pesquisa com estudantes.

## 2. Público e proposta do TestingStudio Web

> O laboratório reúne as técnicas em uma aplicação Python com Streamlit. A sprint 1 trabalha classes de equivalência e valores de fronteira. A sprint 2 transforma o fonte em grafo e calcula a complexidade. A sprint 3 acompanha definições e usos de variáveis e executa mutação em um modelo local. O mesmo editor conecta essas análises. O Gemini pode comentar as evidências quando solicitado.

**Na tela:** mostrar a navegação e o editor compartilhado. Não fazer uma chamada à API durante o pitch, salvo se isso tiver sido preparado e autorizado para a sessão.

## 3. Demonstração em quatro passos

> Primeiro, o plano da regra escrita e sua divergência com o TXT. Depois, o grafo da função de cálculo e sua complexidade. Em seguida, uma definição ligada ao uso da variável. Por fim, a suíte local identifica o original e um mutante que ela distingue. Cada visão está vinculada ao fonte analisado e tem seu próprio limite.

**Passo 1, cerca de 10 segundos:** na sprint 1, localizar o esperado normativo para negativo e a observação sobre o TXT. Mostrar a ambiguidade de NULL.

**Passo 2, cerca de 15 segundos:** na sprint 2, selecionar `cad0001_calcula_valor`, apontar uma decisão e seu desvio; mostrar o valor calculado na tela. No TXT original são três decisões e V(G)=4. Se o fonte estiver editado, explicar o valor atual.

**Passo 3, cerca de 10 segundos:** na sprint 3, mostrar um par Def-Uso e explicar que uma redefinição interrompe o vínculo anterior. Deixar o exemplo preparado para o ensaio.

**Passo 4, cerca de 15 segundos:** mostrar o resultado da suíte previamente executada, apontar um mutante e o caso que o distinguiu; exportar ou abrir a evidência correspondente. Ler os indicadores atuais. Uma execução ao vivo pode ser usada se couber no ensaio cronometrado.

Se a navegação exceder os 50 segundos propostos, usar os relatórios já exportados ou ampliar a duração total. Não omitir a identificação de fonte e suíte para cumprir o cronômetro.

## 4. Evidências disponíveis nesta execução

> O diferencial demonstrado é relacionar essas visões ao mesmo fonte e exportar evidências identificadas. A verificação da ferramenta, a conformidade funcional do CAD0001 e a declaração humana têm resultados próprios. Na RTM funcional, os requisitos levam aos testes e os testes levam aos requisitos. O TXT original diverge da regra de negativos; NULL fica pendente por ambiguidade do manual. Devemos ler as contagens desta execução, inclusive casos não executados. O SHA-256 identifica o texto e o relatório identifica as evidências.

**Na tela, cerca de 45 segundos:** abrir a sprint 4, executar a validação local se ainda não houver resultado atual e ler os dados do slide de evidências. Apontar fonte, suíte e relatório exportado. Se houver aviso de desatualização, gerar uma nova validação antes de apresentar os números.

**Conferência para o ensaio:** no plano completo do TXT original, são 6 PASS, 6 FAIL por negativos e 3 pendências de NULL. Mostrar uma linha funcional e seu requisito. Se houver outra seleção ou edição, usar os números calculados; selecionar apenas os casos que passam não elimina os demais do plano. A suíte de mutação tem outro propósito e não substitui esse esperado funcional.

## 5. Validação e limites do resultado

> O TestingStudio analisa um subconjunto de 4GL e executa um modelo Python restrito do cálculo. Ele não executa o banco ou as transações Informix e não prova que o legado está livre de defeitos. Também não medimos economia de tempo ou satisfação de usuários. Nosso próximo passo é confrontar o laboratório com seu uso real.

**Na tela, cerca de 40 segundos:** mostrar um critério técnico e um cenário AC-01 a AC-06. Distinguir verificação técnica de decisão humana. Não preencher um aceite de demonstração como se fosse a decisão de um avaliador real.

## 6. Pedido e próximo passo

> Pedimos ao avaliador que realize as tarefas propostas, indique se os relatórios são compreensíveis e registre as ressalvas. Pedimos também a confirmação das regras sobre negativos e NULL. Com essa decisão, poderemos ajustar o oráculo e planejar os testes no legado. A entrega oferece código, demonstração e evidências para sustentar essa conversa.

**Na tela, cerca de 35 segundos:** deixar visíveis o plano de aceitação e os downloads. Reservar perguntas para depois dos quatro minutos propostos.

## Respostas de apoio

| Pergunta possível | Resposta fundamentada no projeto |
| --- | --- |
| O programa original foi executado? | Não. O GFC é estático e a mutação usa um modelo local restrito. Os testes no runtime Informix ainda precisam de ambiente e execução. |
| Um escore de 100% comprova qualidade total? | Ele informa que a suíte distinguiu os mutantes considerados elegíveis nessa execução. Outros defeitos, entradas ou operadores podem produzir resultados diferentes. |
| O Gemini decide se a sprint foi aprovada? | Não. Ele fornece um comentário assistido; as evidências locais e a decisão humana devem ser revistas. |
| O usuário ou o professor já aprovou a ferramenta? | Não há essa aprovação registrada. O plano solicita uma avaliação e começa com aceitação pendente. |
| Qual é o ganho de produtividade? | Não foi medido. Podemos investigar essa hipótese em uma avaliação futura com tarefas e participantes definidos. |

## Fontes e preparação do ensaio

A estrutura e a duração proposta foram adaptadas da orientação de [pitch do Sebrae RN](https://blog.rn.sebrae.com.br/pitch/). A distinção usada na avaliação vem de [Product Validation, NASA](https://www.nasa.gov/reference/5-4-product-validation/), e a organização das evidências se apoia no [plano de V&V da NASA](https://www.nasa.gov/reference/appendix-i-verification-and-validation-plan-outline/). Consulta: 19/10/2026.

O conceito de RTM funcional bidirecional foi inspirado na [sprint 4 do projeto indicado pelo usuário](https://github.com/danielgascho/testingstudio-cad0001/blob/1af68b5916271b1540b12fea9e1c5304a02911bf/sprint4.py). O plano, o fonte e os resultados apresentados aqui pertencem à nossa implementação, incluindo a pendência normativa de NULL. Os quatro minutos continuam sendo uma proposta própria.

O conteúdo técnico da fala se refere à implementação e ao TXT do projeto. O [plano da sprint 4](sprint-4.md) explicita hipóteses, tarefas propostas e registros ainda pendentes. Ensaiar com cronômetro e ajustar o tempo de navegação; quatro minutos são uma meta editorial, não uma medição já realizada.
