# Verificação da implementação da sprint 4

Executada em **19/10/2026**. O escopo foi autorizado pelo usuário após não localizar um enunciado específico: pesquisa de pitch/validação e comparação com a [sprint 4 do repositório indicado](https://github.com/danielgascho/testingstudio-cad0001/blob/1af68b5916271b1540b12fea9e1c5304a02911bf/sprint4.py).

## Testes da ferramenta

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=artifacts/sprint4/pytest.xml
.\.venv\Scripts\python.exe validar_entrega.py --junit artifacts/sprint4/pytest.xml
```

Resultado: **182 testes e 6 subtestes aprovados**. O XML contém 188 resultados, sem falhas ou erros. Houve apenas o aviso de depreciação interno já existente do SDK `google-genai`. As chamadas à API foram simuladas.

Os testes cobrem rastreabilidade funcional nos dois sentidos, plano completo/parcial/vazio, casos de oráculo indefinido, alterações de fonte/suíte/seleção, preservação de resultados anteriores, avaliação manual, conteúdo dos pacotes e tratamento de texto nos exports. As sprints anteriores continuam incluídas na suíte.

## Resultado do programa auditado

Este resultado é separado da aprovação dos testes da ferramenta. A ferramenta encontra divergências no programa fornecido; não corrige o fonte para produzir aprovação.

| Item | Resultado no TXT original |
| --- | --- |
| Casos planejados | 15 |
| Casos observados no modelo local | 15 |
| PASS | 6 |
| FAIL | 6, por ausência da rejeição de negativos exigida pela regra escrita |
| Pendentes | 3, pois o retorno esperado de NULL é ambíguo no material |
| REQ-CAD01 · Fórmula válida | Aprovado no plano |
| REQ-CAD02 · Zero | Aprovado no plano |
| REQ-CAD03 · Negativos | Reprovado no plano |
| REQ-CAD04 · NULL | Pendente de definição do contrato |

A suíte separada de caracterização do código passa 8/8 casos e distingue 12/12 mutantes no modelo local. Isso não altera as falhas de conformidade funcional acima.

As nove verificações locais da ferramenta têm sete aprovações e duas pendências: revisão contextual de anomalias estáticas e aceitação manual. Os seis cenários de aceitação permanecem pendentes, sem avaliador ou observação inventados.

## Artefatos gerados

- Relatório: `VAL-dc8eddcbbef1463625a5`.
- Execução: `2026-10-19T20:16:21.359590-03:00`.
- SHA-256 do fonte: `1ecf8cc7ffd7db3c19982eb2888996f510b389006266eb8aa08819ba37fcb267`.
- [Pacote ZIP](../artifacts/sprint4/testingstudio_sprint4.zip), com fonte, evidências, matrizes, cenários, pitch e XML real dos testes.
- [Apresentação HTML](../artifacts/sprint4/pitch.html) e [roteiro Markdown](../artifacts/sprint4/pitch.md).
- [Relatório de validação](../artifacts/sprint4/validacao.md) e [evidências JSON](../artifacts/sprint4/validacao.json).

O hash do fonte dentro do ZIP foi conferido contra o relatório. O XML anexado é idêntico ao produzido pela execução dos testes. O HTML foi aberto em navegador headless e seu primeiro slide inspecionado visualmente; funciona offline, com navegação e impressão.

Os artefatos ficam em `artifacts/sprint4`, diretório ignorado pelo Git, e podem ser regenerados pelo comando acima. A reexecução produz novo horário e identificador de relatório.

Não foram executados Informix-4GL, SQL ou homologação com usuário. As hipóteses e fontes da proposta estão em [sprint-4.md](sprint-4.md).
