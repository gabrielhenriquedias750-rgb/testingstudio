# Sprints 2 e 3 — requisitos e conferência

As referências e seus locais estão em [material-base.md](material-base.md). Este documento separa os requisitos encontrados das convenções adotadas para produzir resultados verificáveis.

## Sprint 2 — caixa branca

Requisitos encontrados: ler o código, construir um Grafo de Fluxo de Controle (GFC), exibi-lo visualmente e calcular automaticamente a complexidade ciclomática de McCabe. As aulas também apresentam caminhos independentes e os critérios todos-nós/todas-arestas.

Convenções de análise:

- Cada função tem uma entrada e uma saída unificadas. Todos os retornos ligam-se à saída da função. Chamadas a outras funções são comandos; seus grafos não são expandidos dentro do chamador.
- Nós e arestas referenciam os comandos e as linhas do fonte. Cada `IF` conta como uma decisão. Uma condição composta conta como um predicado, sem decomposição de curto-circuito.
- Para um GFC conectado por função, `V(G) = E − N + 2`. A equivalência `decisões + 1` serve como conferência para o subconjunto estruturado suportado. Num desenho planar, a contagem de regiões também inclui a região externa. A forma geral para componentes independentes é `E − N + 2P`.
- Entrada e saída devem ser incluídas tanto na contagem de nós quanto na de arestas correspondentes. Trocar essa convenção sem ajustar o grafo produz valores incorretos.
- Uma base de caminhos descreve independência estrutural. A viabilidade de cada caminho depende dos predicados e dos dados de entrada. `V(G)` não mede cobertura observada nem determina sozinho casos executáveis.
- Sintaxe sem suporte deve gerar uma limitação explícita. Um grafo parcial não deve receber uma métrica apresentada como análise completa.

Referência para o TXT fornecido, contando somente os `IF` explícitos:

| Função | Decisões | V(G) esperado |
| --- | ---: | ---: |
| `cad0001_main` | 0 | 1 |
| `cad0001_calcula_valor` | 3 | 4 |
| `cad0001_incluir` | 2 | 3 |
| `cad0001_alterar` | 2 | 3 |
| `cad0001_excluir` | 2 | 3 |

Conferência técnica: comparar o GFC com o fonte, verificar os destinos verdadeiro/falso e os retornos antecipados, conferir as duas contagens de complexidade e inspecionar a base de caminhos. Para afirmar cobertura de nós ou arestas, é necessário registrar execuções e comparar os elementos visitados com os elementos exigidos.

## Sprint 3 — fluxo de dados e mutação

Requisitos encontrados: identificar pares Def-Uso, rastrear fluxo de dados e implementar testes de mutação com cálculo do escore. A aula complementa o rastreio com definições, usos computacionais (`c-use`) e usos predicativos (`p-use`).

Convenções de fluxo de dados:

- Um parâmetro de entrada é uma definição na entrada da função. Atribuições definem o destino e usam as variáveis da expressão. Um uso à direita de uma atribuição ocorre antes da nova definição do destino.
- Usos computacionais referenciam nós; usos predicativos referenciam as arestas de saída da decisão.
- Um par Def-Uso requer um caminho da definição ao uso sem redefinição intermediária da mesma variável. A relação é local à função; efeitos de SQL, chamadas externas e estado global requerem indicação dos limites de modelagem.
- A tabela deve permitir relacionar variável, definição, uso, tipo de uso e caminho/aresta. Alertas de definição sem uso ou uso sem definição são indícios para revisão, e não defeitos confirmados por execução.
- Os critérios todos-usos, todos-usos-predicativos/alguns-computacionais e todos-usos-computacionais/alguns-predicativos descrevem obrigações de teste. Extrair as obrigações não comprova que foram cobertas.

Conferência técnica: acompanhar as três definições de parâmetros até os testes de nulo e até a fórmula; verificar que o ramo que atribui zero substitui a definição anterior; conferir os dois destinos de cada uso predicativo. Comparar pares extraídos com o grafo e com as linhas do código.

Na mutação, a aula apresenta AOR (operadores aritméticos), ROR (relacionais), COR (condicionais/lógicos) e LVR (valores literais). O escopo implementado deve identificar os operadores efetivamente aplicáveis ao modelo analisado.

Para cada execução, guardar a suíte e seus valores esperados, o fonte analisado e os resultados por mutante. O escore da suíte completa requer que ela passe no programa original. Quando há falhas no original, a aplicação informa essas falhas e calcula somente um escore parcial sobre os casos em que o original satisfaz o esperado, indicando quantos foram usados. Esse resultado não representa a eficácia da suíte completa. Se nenhum caso for elegível, o escore fica indisponível. Um mutante é morto quando ao menos um caso elegível produz comportamento diferente do oráculo adotado.

O escore é `MS = Md / (Mt − Me) × 100`, sendo `Md` os mutantes mortos, `Mt` o total de mutantes válidos executáveis e `Me` os equivalentes confirmados. Mutantes inválidos são registrados separadamente e excluídos antes de formar `Mt`. Sobrevivência não prova equivalência; exclusões por equivalência precisam de justificativa. Se o denominador for zero, o escore é indisponível.

Conferência técnica: verificar resultados do original, alterações individuais e contagem de mortos/sobreviventes/equivalentes/inválidos. Confirmar que os casos que mataram cada mutante são rastreáveis e que alterar fonte, suíte ou revisão de equivalência exige nova execução.

## Limites dos resultados

A análise estática lê o subconjunto 4GL suportado; ela não executa Informix-4GL nem SQL. Uma execução de um modelo local de `cad0001_calcula_valor` verifica esse modelo e sua suíte. Ela não comprova o comportamento do banco, atomicidade de transações, integração com Logix, limites numéricos ou arredondamento do runtime de produção.

No ambiente real, a validação transacional precisaria observar falhas na primeira e na segunda operação SQL, ausência de gravação parcial após rollback e sucesso de inclusão/alteração/exclusão. Esses cenários são uma proposta técnica derivada do código, não critérios de entrega localizados para a sprint 4.

Relatórios de IA podem explicar os resultados calculados. O GFC, as métricas, os pares e os resultados de execução devem continuar rastreáveis ao fonte e à suíte, com as limitações visíveis.
