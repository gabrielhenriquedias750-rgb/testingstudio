# TestingStudio Web — Sprints 1 a 4

Ferramenta web em **Python + Streamlit** para testar o programa CAD0001. A sprint 1 cobre caixa-preta; a sprint 2 acrescenta GFC e complexidade de McCabe; a sprint 3 acrescenta Def-Uso e teste de mutação. Usa a API Gemini pelo SDK oficial `google-genai`, com análises locais disponíveis sem chave.

As sprints 2 e 3 seguem o `TestingStudio_Web_Kickoff.pptx` e as aulas fornecidas em Downloads. As referências estão em [docs/material-base.md](docs/material-base.md). A sprint 4 foi implementada por solicitação do usuário com pesquisa externa de pitch e validação. Seu escopo é uma proposta do projeto: não foi localizado um enunciado específico do professor.

## Abrir no Windows

É necessário Python 3.11 ou superior e internet para instalar as dependências. Abra um terminal **PowerShell** na pasta do projeto e prepare o ambiente na primeira execução:

```powershell
py -3 -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
```

Para iniciar, execute:

```powershell
& ".\.venv\Scripts\python.exe" -m streamlit run app.py
```

Depois, acesse **http://localhost:8501** no navegador.

O inicializador **`iniciar.ps1`** também prepara o ambiente virtual e instala dependências quando necessário:

```powershell
.\iniciar.ps1
```

O script PowerShell executa o Python diretamente. Se scripts `.ps1` forem restringidos pela política da máquina, use o comando direto acima em um terminal permitido. Não é necessário alterar políticas do sistema.

O arquivo `iniciar.bat` depende do Prompt de Comando. Se aparecer **“O prompt de comando foi desativado pelo administrador”**, use a opção PowerShell; o `.bat` não funciona com esse bloqueio.

Interrompa o servidor com `Ctrl+C` no terminal.

## Sprint 1 · Caixa-preta

Selecione **Sprint 1 · Caixa-preta** na barra lateral. O fluxo já existente continua disponível:

1. Confira o TXT original no editor. O arquivo real fornecido acompanha o projeto, sem alterações; a leitura usa um caminho relativo ao `app.py`.
2. Insira sua chave do [Google AI Studio](https://aistudio.google.com/apikey) na barra lateral. O campo é protegido por senha. O modelo inicial é `gemini-3.8-flash`. Em **Configuração do modelo**, use **Consultar modelos da chave** para selecionar um modelo de texto retornado pela API, ou informe seu identificador no campo **Modelo Gemini**.
3. Clique em **Executar auditoria de caixa-preta**. Esse comando envia ao Gemini o conteúdo atual do editor e gera o relatório em português.
4. Consulte as abas **Relatório (PCE & AVL)**, **Gráfico de fronteira** e **Casos de teste**. Exporte o relatório em Markdown e os casos em CSV.

O modo **Preparação local (sem API)** gera um relatório determinístico com PCE, AVL e observações estáticas, sem usar Gemini. As tabelas e os gráficos também podem ser consultados antes da primeira auditoria. A interface identifica a origem de cada relatório; o modo local não substitui a integração exigida pelo PDF.

## Sprint 2 · Caixa-branca

Selecione **Sprint 2 · Caixa-branca** e escolha uma função. O editor é compartilhado entre as sprints. O motor constrói o grafo a partir do texto atual e apresenta nós, arestas, decisões, **V(G) = E − N + 2** e uma base de caminhos independentes. Exporte o GFC em DOT e as evidências em JSON ou Markdown.

Cada função tem entrada e saída unificadas. No TXT original, `cad0001_main` tem V(G)=1, `cad0001_calcula_valor` tem V(G)=4 e as três operações de cadastro têm V(G)=3. Os caminhos são estruturais: sua viabilidade e cobertura em execução dependem de testes no legado. Construções não suportadas são sinalizadas; o motor não interpreta todo o Informix-4GL.

## Sprint 3 · Fluxo de dados e mutação

Selecione **Sprint 3 · Fluxo de dados e mutação**. A aba **Definições e usos** apresenta pares Def-Uso livres de redefinição, com c-use em comandos e p-use em arestas de decisão, além dos pontos de revisão estática.

Na aba **Mutação e escore**, edite a suíte CSV (`id;p1;p2;p3;expected`) e clique em **Executar suíte e mutantes**. Use `NULL` nas entradas nulas. A suíte inicial caracteriza o comportamento do TXT; seu oráculo é diferente da regra teórica de negativos da sprint 1. O resultado mostra o original contra os valores esperados, as alterações de cada mutante e os casos que os distinguiram.

O cálculo usa **MS = mortos / (total − inválidos − equivalentes)**. Equivalência exige revisão manual e justificativa. Uma execução sem denominador válido não produz percentual. A mutação executa um modelo local restrito da função de cálculo com `Decimal`; ela não compila nem executa 4GL ou SQL e não reproduz overflow ou arredondamento do runtime original.

O aplicativo sinaliza resultados anteriores quando o fonte, a suíte ou a revisão de equivalência mudam. Os downloads incluem a identificação do fonte e da execução. Em ambas as sprints, **Gerar análise com Gemini** envia o fonte e as evidências locais somente após o clique, usando a chave e o modelo da barra lateral.

Consulte [o roteiro das sprints 2 e 3](docs/sprints-2-3.md) para referências e validação manual.

## Sprint 4 · Pitch e validação

Selecione **Sprint 4 · Pitch e validação**. As abas **Pitch e demonstração**, **Validação técnica** e **Aceitação e entrega** permitem consultar o pitch, executar verificações locais, revisar a rastreabilidade e registrar a avaliação manual. Clique em **Executar validação local** para obter as evidências do fonte e da suíte atuais. O pitch pode ser exportado em HTML/Markdown; o pacote ZIP reúne fonte, identificadores, RTM, relatórios, aceitação e apresentação.

A demonstração proposta dura aproximadamente quatro minutos e apresenta o problema, a solução, as evidências e o pedido de avaliação. O texto pronto está em [docs/pitch-testingstudio.md](docs/pitch-testingstudio.md). A sprint 4 funciona sem API; repita a validação local quando fonte ou suíte mudar.

Na aba técnica, a verificação da ferramenta é apresentada separadamente da conformidade funcional do CAD0001. A RTM funcional liga requisitos aos **15 casos da sprint 1** e cada caso aos seus requisitos. Em **Casos do plano funcional**, casos desmarcados continuam pendentes no plano. Com o TXT original e todos selecionados, a conferência é 6 PASS, 6 FAIL por negativos e 3 pendências de NULL; os valores exibidos refletem a execução atual. Essa ampliação usa como referência conceitual a [RTM de sprint4.py indicada pelo usuário](https://github.com/danielgascho/testingstudio-cad0001/blob/1af68b5916271b1540b12fea9e1c5304a02911bf/sprint4.py), preservando o fonte e a ambiguidade do nosso manual.

Os indicadores automáticos verificam o escopo local da aplicação. A aceitação por uma pessoa começa **pendente** e exige observação, evidência e decisão registrada. Não houve homologação do professor nem execução do Informix-4GL nesta entrega. O [plano da sprint 4](docs/sprint-4.md) descreve as hipóteses, os critérios propostos e as referências Sebrae/NASA usadas na pesquisa.

Para gerar o pacote e o pitch sem abrir a interface:

```powershell
.\.venv\Scripts\python.exe validar_entrega.py
```

Os arquivos são gravados em `artifacts/sprint4`: pacote ZIP, pitch HTML/Markdown, validação JSON/Markdown, matriz técnica, duas matrizes funcionais e registros de aceitação em CSV. O argumento opcional `--junit artifacts/sprint4/pytest.xml` anexa um XML existente de uma execução real de testes; o script não executa pytest. O pacote conserva as falhas funcionais e a aceitação pendente.

A execução e as evidências desta implementação estão em [docs/validacao-sprint-4.md](docs/validacao-sprint-4.md).

### Erro de modelo não encontrado (404)

O `gemini-2.5-flash` citado no manual tem [acesso restrito pelo Google a usuários que já o utilizavam](https://ai.google.dev/gemini-api/docs/deprecations). Uma chave preenchida não garante acesso a esse modelo. O aplicativo usa agora `gemini-3.8-flash` como padrão e atualiza o antigo padrão em sessões já abertas, preservando identificadores personalizados.

Se aparecer o erro de modelo não encontrado, abra **Configuração do modelo**, clique em **Consultar modelos da chave** e escolha outro modelo de texto. A consulta não envia o código-fonte nem gera relatórios. Ela lista metadados fornecidos pela API; aparecer na lista não garante autorização para gerar conteúdo nem cota. O aplicativo usa somente o modelo selecionado, sem tentar outros automaticamente. Ao trocar a chave, a lista consultada é descartada.

Opcionalmente, configure `GEMINI_API_KEY` no ambiente ou em `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "sua-chave"
```

O arquivo de segredos está no `.gitignore`. A aplicação não grava a chave informada pela interface em arquivos nem a inclui nos relatórios. Relatórios e edições permanecem apenas na sessão; use os downloads para guardá-los.

## Requisitos atendidos

| Requisito do PDF | Implementação |
| --- | --- |
| Ler e exibir `cad0001_item_calculo.txt` | Leitura do arquivo real, editor e restauração do original |
| Python, Streamlit e Gemini | `app.py` e serviço com SDK `google-genai` |
| PCE dos três parâmetros | Matriz com valores não negativos, negativos e nulos |
| AVL com ε = 0,01 | Justificativa para duas casas decimais e quatro pontos obrigatórios |
| Dashboard gráfico | Gráfico completo, ampliação em torno do zero e tabela |

Há 15 casos de teste propostos: On (0,00), Off (-0,01), Interior (100,00), Exterior (-100,00) e NULL para cada parâmetro. A base é `(1,00; 1,00; 0,00)`, variando apenas uma entrada por vez. Os cálculos esperados usam `Decimal`.

## Divergências do material

- A teoria do manual exige rejeitar negativos com `-1`. O TXT fornecido aplica `(p1 * p2) + p3` sem essa guarda. O aplicativo preserva o arquivo e destaca a divergência.
- A teoria classifica nulos como inválidos, mas tanto o exemplo do PDF quanto o TXT os transformam em zero. O retorno esperado para NULL aparece como **A esclarecer**, pois o material não define uma regra consistente.

A ferramenta analisa o texto e propõe testes. **Ela não executa Informix-4GL, SQL ou transações do programa original.** A inspeção local reconhece somente padrões explícitos na função de cálculo e não é um interpretador 4GL. Ausência de um padrão reconhecido exige revisão. Casos esperados não são apresentados como resultados observados. Overflow, arredondamento do runtime e operações de cadastro exigem testes adicionais no ambiente legado.

Ao editar ou importar outro fonte (`.txt`/`.4gl`, até 100 KB), a interface indica se o último relatório ficou desatualizado. Cada relatório exportado registra a origem, o modelo, o horário em São Paulo e o SHA-256 do texto analisado.

## Estrutura e validação

```text
app.py                       Interface Streamlit
audit.py                     PCE, AVL, casos e análise local
structural.py                GFC, McCabe, Def-Uso e motor de mutação
sprint_views.py              Interfaces e exportações das sprints 2 e 3
delivery.py                  Evidências e rastreabilidade da sprint 4
gemini_service.py            Integração Gemini e tratamento de erros
cad0001_item_calculo.txt      Arquivo original analisado
assets/styles.css            Estilos da interface
.streamlit/config.toml       Tema e configuração
tests/                       Testes de domínio, serviço e interface
docs/                        Material-base, roteiros, pitch e plano de validação
iniciar.ps1                  Inicialização pelo PowerShell
iniciar.bat                  Alternativa para máquinas com cmd.exe permitido
```

Execute os testes:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes da integração usam respostas simuladas, sem consumir API. Uma chamada real requer sua chave, acesso ao modelo e cota disponível. Erros de autenticação, cota, indisponibilidade e timeout são exibidos sem detalhes de credenciais.

O resultado da verificação das sprints 2 e 3 está em [docs/validacao-sprints-2-3.md](docs/validacao-sprints-2-3.md).

Referências técnicas: [SDK oficial Google Gen AI](https://googleapis.github.io/python-genai/) e [AppTest do Streamlit](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).

O projeto usa um servidor Python para executar a aplicação Streamlit. Para hospedá-lo, utilize um ambiente com suporte a processos Python; hospedagem estática como GitHub Pages não executa esse servidor.
#   t e s t i n g s t u d i o  
 #   t e s t i n g s t u d i o  
 