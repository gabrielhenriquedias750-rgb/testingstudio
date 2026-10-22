# Sprint 4 — Pitch e validação

## Origem e decisões desta entrega

Esta sprint foi criada por solicitação do usuário, que autorizou pesquisar e implementar pitch e validação mesmo sem um enunciado específico do professor. A revisão dos arquivos de Downloads não localizou esse enunciado. O escopo abaixo é uma proposta do projeto; a duração, os critérios de aceitação e o roteiro não são exigências atribuídas à disciplina.

As hipóteses adotadas são: apresentação acadêmica para estudantes e avaliador, demonstração local do TestingStudio Web e aproximadamente quatro minutos de fala e navegação. O público e a utilidade educacional ainda precisam de confirmação com pessoas que usarão a ferramenta. Não foram levantados tamanho de mercado, economia de tempo, receita ou adesão de usuários.

## Fundamentação pesquisada

O [Sebrae RN](https://blog.rn.sebrae.com.br/pitch/) orienta um pitch objetivo, adequado à audiência, com problema, solução, diferenciais e pedido. A faixa de três a cinco minutos apresentada na fonte motivou nossa proposta de quatro minutos. O [roteiro pronto](pitch-testingstudio.md) aplica essa estrutura ao produto existente.

A [NASA distingue verificação de validação](https://www.nasa.gov/reference/5-4-product-validation/): a primeira confronta requisitos; a segunda avalia o uso pretendido e as expectativas das pessoas no ambiente previsto. Seu [modelo de plano de V&V](https://www.nasa.gov/reference/appendix-i-verification-and-validation-plan-outline/) inclui métodos, responsabilidades, condições e matrizes vinculadas aos resultados. Adaptamos essas ideias à escala deste laboratório, sem alegar certificação ou conformidade com um processo NASA.

A referência indicada pelo usuário, [sprint4.py do projeto de Daniel Gascho](https://github.com/danielgascho/testingstudio-cad0001/blob/1af68b5916271b1540b12fea9e1c5304a02911bf/sprint4.py), aplica uma RTM funcional nos dois sentidos: requisitos para casos e casos para requisitos. Esse conceito orientou a ampliação da entrega; o código foi escrito para o fonte, o plano e os oráculos deste projeto. A referência adota rejeição de NULL e um modelo que rejeita negativos. Nosso TXT não tem a guarda de negativos e nosso manual é ambíguo sobre NULL, portanto os resultados e o oráculo precisam refletir essas diferenças. Mantivemos os quatro minutos como proposta própria de apresentação.

Fontes consultadas em 19/10/2026. As aulas fornecidas continuam sendo a base das sprints 1 a 3; veja [material-base.md](material-base.md).

## Produto entregue

A área **Sprint 4 · Pitch e validação** tem três abas: **Pitch e demonstração**, **Validação técnica** e **Aceitação e entrega**. Reúne a apresentação, as evidências locais do fonte atual e a rastreabilidade entre critérios propostos e verificações. O roteiro também está disponível neste repositório para preparação e ensaio.

Clique em **Executar validação local** para conferir propriedades do modelo e dos relatórios produzidos pela aplicação. A aba técnica apresenta a matriz de verificação da ferramenta e a RTM funcional do CAD0001. O resultado deve ser lido junto de sua versão de fonte, suítes, seleção de casos, horário e limitações. Se algum desses dados mudar, execute novamente antes de usar as métricas da apresentação.

Na aba de aceitação, **Registrar avaliação** exige responsável e observação para registrar aprovação ou reprovação de um cenário. O registro conserva data, fonte e identificação do relatório. Abrir a tela ou obter resultados automáticos positivos não constitui aceitação pelo usuário. A sprint 4 funciona localmente, sem chamada ao Gemini.

## Três resultados com escopos próprios

| Resultado | Pergunta respondida | Evidência e limite |
| --- | --- | --- |
| Verificação técnica da ferramenta | As análises e os cálculos locais são coerentes com seus contratos? | Matriz de checks S1/S2/S3/S4, hashes, GFC, base, Def-Uso, suíte de caracterização e contagens dos mutantes. Não aprova as regras funcionais do CAD0001. |
| Conformidade funcional do CAD0001 | A saída do modelo do fonte satisfaz o esperado do plano da sprint 1? | Comparação de esperado/obtido para os 15 casos planejados, com RTM requisito→casos e caso→requisitos. Usa o modelo local restrito, sem execução nativa 4GL. |
| Declaração manual de aceitação | A pessoa avaliadora considera o uso demonstrado adequado? | Cenários AC-01 a AC-06 com responsável, observação, decisão e vínculo à execução. O sistema conserva a declaração, sem comprovar a sessão ou conceder homologação por conta própria. |

A suíte de mutação caracteriza o comportamento original para medir a sensibilidade aos mutantes. O plano funcional usa o esperado normativo da sprint 1. Por isso o modelo pode satisfazer a suíte de caracterização e, ao mesmo tempo, reprovar casos funcionais de negativos. Isso evidencia uma divergência do programa auditado; não equivale a uma falha do mecanismo de comparação.

### RTM funcional e execução parcial

O plano funcional conserva os 15 casos da sprint 1: On-Point, Off-Point, Interior, Exterior e Nulo para cada parâmetro. As regras organizam cálculo nominal, zero válido, rejeição dos negativos e esclarecimento do tratamento de NULL. Cada caso mostra seus requisitos, entradas, esperado, obtido e estado; cada requisito mostra os casos associados e suas pendências.

Em **Casos do plano funcional**, é possível selecionar todos, um subconjunto ou nenhum caso. Os casos desmarcados permanecem no plano como não executados. Um vínculo na RTM ou a aprovação dos poucos casos selecionados não aprova os demais nem o requisito completo. Um caso sem oráculo definido permanece pendente, mesmo quando há resultado observado no modelo.

Com o TXT original e o plano completo, a referência de conferência é **6 PASS, 6 FAIL e 3 pendentes**: zero/interior satisfazem o cálculo; negativos divergem do retorno normativo `-1`; NULL conserva a pendência de requisitos. Os três casos NULL não recebem automaticamente o oráculo `-1` adotado pelo repositório de referência. As contagens apresentadas devem vir da execução atual e podem mudar com o fonte ou a seleção.

## Plano proposto para a sessão de avaliação

**Objeto:** versão atual do TestingStudio Web e fonte exibido no editor. **Ambiente:** navegador e servidor Streamlit no computador de demonstração. **Responsáveis propostos:** apresentador opera a ferramenta; avaliador observa ou executa as tarefas e decide o aceite. Preencher os nomes somente quando houver participantes reais.

Antes da sessão, restaure o TXT original, selecione o modo local, execute a suíte de mutação e baixe as evidências. Se usar um fonte editado, identifique a alteração e confira o SHA-256 correspondente. Uma avaliação com outro fonte ou outra suíte é uma nova configuração e deve conservar esse contexto.

Os cenários abaixo usam os mesmos identificadores de `acceptance_template` em `delivery.py` e da interface. São critérios sugeridos, não uma rubrica oficial nem resultados já observados.

| Critério proposto | Tarefa e evidência a registrar | Aceite esperado | Estado humano inicial |
| --- | --- | --- | --- |
| AC-01 · Rastrear fonte, suíte e relatório | Gerar uma validação, conferir fonte/SHA-256/relatório e comparar com nova execução após uma edição. | Reconhece o contexto de cada execução e a necessidade de atualizar evidências. | Pendente |
| AC-02 · Explicar caixa-branca usando o grafo | Contar nós, arestas e decisões, conferir V(G), percorrer uma base e recalcular após acrescentar um IF suportado. | Relaciona o fonte às contagens sem afirmar cobertura executada no legado. | Pendente |
| AC-03 · Inspecionar Def-Uso e redefinições | Seguir um par DU, inserir uma redefinição e justificar os achados da nova análise. | Explica a interrupção do vínculo anterior e identifica p-use em aresta. | Pendente |
| AC-04 · Avaliar a suíte por mutação | Conferir o original, inspecionar um mutante e observar sobreviventes com uma suíte fraca. | Explica o oráculo, os resultados e o denominador do escore no modelo. | Pendente |
| AC-05 · Confirmar a regra de negócio de NULL e negativos | Comparar manual/TXT, pedir decisão ao responsável pela regra e revisar a suíte. | Registra o contrato aceito e preserva as divergências identificadas. | Pendente |
| AC-06 · Validar a demonstração no ambiente pretendido | Percorrer as técnicas e exportações no navegador, apresentar o pitch e registrar dúvidas e decisão. | Há decisão fundamentada com ambiente e escopo, inclusive ressalvas ou reprovação. | Pendente |

Não preencher resultados antecipadamente. Se uma tarefa falhar, registrar a condição, o esperado, o observado, a evidência e a correção proposta; repetir depois da alteração sem apagar o registro anterior. Se não houver avaliador, conservar **Pendente**.

Os cenários AC são manuais. A matriz técnica do aplicativo contém os seguintes IDs, com esperado, observado e evidência calculada:

| ID da RTM | Objeto da verificação local |
| --- | --- |
| S4-01 | Vínculo dos snapshots de fonte e suíte por SHA-256. |
| S1-01 | Integridade do plano PCE/AVL, sem execução 4GL desses casos. |
| S2-01 | Conectividade do GFC e coerência de N/E/V(G). |
| S2-02 | Validade e independência da base de caminhos do modelo. |
| S3-01 | Integridade dos pares Def-Uso e caminhos sem redefinição. |
| S3-02 | Resultado do original do modelo contra a suíte informada. |
| S3-03 | Contabilização dos mutantes e reprodução do escore. |
| S3-04 | Identificação das anomalias que exigem revisão contextual. |
| S4-02 | Obrigação de avaliação humana; permanece pendente na verificação automática. |

## Evidências e decisão

Para uma sessão reproduzível, guardar fonte/SHA-256, suíte de mutação, seleção do plano funcional, relatórios das verificações locais, as duas matrizes e registros manuais, além de ambiente, participante e horário. A aplicação exporta o pitch em HTML ou Markdown e um pacote ZIP com fonte, identificadores, RTM, relatórios, aceitação e pitch. Os downloads conservam o trabalho fora da sessão do aplicativo. Não incluir chaves da API nos registros.

Também é possível gerar os artefatos sem abrir o navegador:

```powershell
.\.venv\Scripts\python.exe validar_entrega.py
```

A pasta padrão `artifacts/sprint4` recebe `testingstudio_sprint4.zip`, `pitch.html`, `pitch.md`, `validacao.json`, `validacao.md`, `rastreabilidade.csv`, `funcional_requisitos.csv`, `funcional_casos.csv` e `aceitacao.csv`. O pacote preserva resultados reprovados e pendências. Para anexar um XML de testes já executados, use `--junit artifacts/sprint4/pytest.xml`; esse argumento lê o arquivo existente e não executa pytest. O registro da execução final dos testes deve informar seu resultado e ambiente separadamente.

A verificação automatizada existente das sprints 2 e 3 está documentada em [validacao-sprints-2-3.md](validacao-sprints-2-3.md). Esse registro é evidência técnica histórica; a decisão de aceitação humana desta sprint continua pendente até a sessão acima. Uma resposta gerada pelo Gemini também exige revisão e não decide o aceite.

## Riscos que precisam permanecer visíveis

- O modelo local executa somente o subconjunto de cálculo suportado. Informix-4GL, banco de dados e transações não são executados pela aplicação.
- Caminhos estruturais e pares Def-Uso não demonstram que entradas reais percorrem todas as rotas no legado.
- Um escore elevado descreve a suíte e os mutantes gerados; não prova ausência de defeitos ou aceitação pelo usuário.
- Negativos e NULL têm divergências entre manual e TXT. A decisão sobre o oráculo permanece uma questão de requisitos.
- Overflow, arredondamento do runtime, rollback e consistência entre tabelas exigem testes no ambiente Informix/Logix.
- Clareza do pitch, acessibilidade e utilidade educacional exigem observação humana. Não há homologação do professor ou validação externa registrada nesta entrega.
