# Verificação técnica das sprints 2 e 3

Executada em 19/10/2026 no ambiente virtual do projeto. Este registro verifica a implementação dos módulos 2 e 3; a sprint 4 permanece aguardando seu material.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Resultado: **131 testes aprovados**, além de 6 subtestes. Há um aviso de depreciação interno do SDK `google-genai`, sem falhas. Os 82 testes anteriores continuam passando.

## Evidências do TXT fornecido

| Função | Nós | Arestas | V(G) | Caminhos independentes | Pares Def-Uso |
| --- | ---: | ---: | ---: | ---: | ---: |
| `cad0001_main` | 4 | 3 | 1 | 1 | 0 |
| `cad0001_calcula_valor` | 10 | 12 | 4 | 4 | 13 |
| `cad0001_incluir` | 21 | 22 | 3 | 3 | 18 |
| `cad0001_alterar` | 21 | 22 | 3 | 3 | 18 |
| `cad0001_excluir` | 20 | 21 | 3 | 3 | 10 |

Contagem com entrada e saída unificadas, IF como predicado único e p-use por aresta. A base de caminhos tem posto completo no modelo estrutural. Isso não representa cobertura observada no Informix-4GL.

Na mutação do modelo local, a suíte inicial passa **8 de 8 casos** no original e distingue **12 de 12 mutantes**, sem inválidos ou equivalentes declarados: MS local de 100%. Esse resultado se refere apenas aos operadores gerados e aos casos fornecidos, sem comprovar ausência de defeitos no legado.

## Escopo verificado

- GFC e métricas recalculados após edição do fonte; ramos ELSE, retornos antecipados e sintaxe sem suporte.
- Def-Uso com redefinição, c-use, p-use em arestas, usos sem definição e inicialização explícita para NULL.
- Mutantes mortos, sobreviventes, inválidos, revisão de equivalência e oráculos incorretos, incluindo ausência de escore quando nenhum caso é elegível.
- Regressões para operadores dentro de comentários, campos RECORD em maiúsculas e uso anterior de destino em SELECT INTO.
- Navegação pelas três sprints com preservação do editor; exportações com proveniência e aviso de resultados desatualizados.
- Integração Gemini com respostas simuladas, envio somente por clique e tratamento de falhas sem expor credenciais.

Não foi realizada chamada real ao Gemini. Informix-4GL, SQL e banco não foram executados. As limitações estão descritas em [sprints-2-3.md](sprints-2-3.md).
