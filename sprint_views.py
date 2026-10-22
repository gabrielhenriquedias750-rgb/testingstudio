"""Interface das sprints estruturais; os cálculos ficam em structural.py."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from audit import validate_source
from gemini_service import AuditServiceError, generate_sprint_report
from structural import analyze_source, cfg_dot, default_mutation_cases, run_mutation_analysis


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def suite_csv(cases: list[dict]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["id", "p1", "p2", "p3", "expected"])
    for case in cases:
        writer.writerow([case["id"], *("NULL" if x is None else x for x in case["inputs"]), case["expected"]])
    return output.getvalue()


def parse_suite(text: str) -> list[dict]:
    """CSV explícito: NULL só nas entradas; nenhum conteúdo é executado."""
    if len(text) > 100_000:
        raise ValueError("A suíte deve ter no máximo 100.000 caracteres.")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if reader.fieldnames != ["id", "p1", "p2", "p3", "expected"]:
        raise ValueError("Use o cabeçalho id;p1;p2;p3;expected, separado por ponto e vírgula.")
    cases = []
    identifiers = set()
    for row in reader:
        if None in row or any(value is None or not value.strip() for value in row.values()):
            raise ValueError("Preencha todas as cinco colunas; use NULL para entrada nula.")
        identifier = row["id"].strip()
        if identifier in identifiers:
            raise ValueError(f"O identificador {identifier} está repetido.")
        identifiers.add(identifier)
        cases.append({
            "id": identifier,
            "inputs": [None if row[key].strip().upper() == "NULL" else row[key].strip().replace(",", ".") for key in ("p1", "p2", "p3")],
            "expected": row["expected"].strip().replace(",", "."),
        })
        if len(cases) > 100:
            raise ValueError("Use até 100 casos por execução local.")
    if not cases:
        raise ValueError("Adicione pelo menos um caso à suíte.")
    return cases


def _table(rows: list[dict]) -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.caption("Nenhum registro neste escopo.")


def local_report(sprint: int, analysis: dict, mutation: dict | None = None, source_name: str = "Editor CAD0001") -> str:
    lines = [f"# TestingStudio Web — Sprint {sprint}",
             f"Origem: análise local · Arquivo: {source_name}",
             f"Gerado em: {datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat(timespec='seconds')}",
             f"SHA-256 do fonte: `{analysis['source_sha256']}`",
             "Análise estática do subconjunto 4GL suportado. SQL e Informix-4GL não foram executados.",
             "## Complexidade e caminhos"]
    for function in analysis["functions"]:
        lines.append(f"### {function['name']}")
        if not function["supported"]:
            lines.append("Análise indisponível: " + "; ".join(function["errors"]))
            continue
        metric = function["metrics"]
        lines.append(f"N={metric['nodes']}; E={metric['edges']}; V(G)={metric['cyclomatic']}. Fórmula: E−N+2, com entrada e saída únicas.")
        lines.append("Caminhos estruturais independentes (viabilidade de entrada não comprovada):")
        for path in function["basis_paths"]:
            lines.append(f"- {path['id']}: " + " → ".join(map(str, path["nodes"])))
        if sprint == 3:
            lines.append("Pares Def-Uso e anomalias, com nós/linhas de referência:\n```json\n" + _json({"def_use": function["def_use"], "anomalies": function["anomalies"]}) + "\n```")
        lines.extend(function.get("limitations", []))
    if mutation:
        lines.extend(["## Mutação no modelo local da função de cálculo", "```json\n" + _json(mutation) + "\n```"])
    lines.extend(["## Limitações", *analysis.get("limitations", [])])
    return "\n\n".join(lines) + "\n"


def _editor(restore_source, import_upload) -> str:
    with st.expander("Código-fonte compartilhado entre as sprints"):
        st.text_area("Fonte CAD0001", key="source_editor", height=260, max_chars=100_000)
        st.caption(f"Arquivo: {st.session_state['source_name']}")
        st.button("Restaurar TXT original", key="restore_source", on_click=restore_source)
        st.file_uploader("Arquivo CAD0001 (.txt ou .4gl)", type=["txt", "4gl"], key="source_upload", on_change=import_upload)
        if st.session_state.get("upload_error"):
            st.error(st.session_state["upload_error"])
    return st.session_state["source_editor"]


def _function_picker(analysis: dict, sprint: int) -> dict:
    names = [item["name"] for item in analysis["functions"]]
    default = names.index("cad0001_calcula_valor") if "cad0001_calcula_valor" in names else 0
    name = st.selectbox("Função analisada", names, index=default, key=f"structural_function_{sprint}")
    return next(item for item in analysis["functions"] if item["name"] == name)


def _control_flow(function: dict) -> None:
    metric = function["metrics"]
    columns = st.columns(4)
    for column, label, value in zip(columns, ["Nós (N)", "Arestas (E)", "Decisões", "V(G) = E − N + 2"],
                                    [metric["nodes"], metric["edges"], metric["decisions"], metric["cyclomatic"]]):
        column.metric(label, value)
    st.caption("Uma entrada e uma saída unificada por função. Cada IF é uma decisão; expressões compostas são tratadas como um único predicado.")
    graph, paths, details = st.tabs(["Grafo de fluxo de controle", "Caminhos independentes", "Nós e arestas"])
    dot = cfg_dot(function)
    with graph:
        # Aplica as cores apenas na exibicao; o DOT exportado permanece original.
        display_dot = dot.replace(
            "digraph CFG {",
            'digraph CFG {\ngraph [bgcolor="#101214"];'
            ' node [color="#a1a8b2", fontcolor="#e7e9ec"];'
            ' edge [color="#a1a8b2", fontcolor="#a1a8b2"];',
            1,
        )
        st.graphviz_chart(display_dot, width="stretch")
        st.download_button("Baixar GFC (.dot)", dot, f"{function['name']}.dot", key="download_cfg")
    with paths:
        st.info(f"V(G) = {metric['cyclomatic']} é a dimensão da base estrutural de caminhos. Converter essa base em casos executáveis exige verificar os predicados e a viabilidade de cada caminho.")
        if not metric.get("basis_complete", True):
            st.warning("A base extraída está incompleta. Consulte o JSON e revise o grafo antes de definir os testes.")
        _table([{"Caminho": item["id"], "Nós": " → ".join(map(str, item["nodes"]))} for item in function["basis_paths"]])
        st.caption("Caminhos independentes não significam cobertura observada. Não houve execução do legado.")
    with details:
        st.markdown("**Nós, comandos e linhas**")
        _table(function["nodes"])
        st.markdown("**Arestas**")
        _table(function["edges"])


def _mutation(source: str, source_digest: str) -> dict | None:
    st.subheader("Teste de mutação")
    st.caption("Execução de um modelo local restrito de cad0001_calcula_valor, com Decimal. O modelo não reproduz o runtime Informix nem suas transações.")
    st.info("A suíte inicial caracteriza o TXT fornecido. Sua regra de NULL e negativos pode divergir do oráculo da sprint 1; revise os valores esperados antes de avaliar o escore.")
    st.session_state.setdefault("mutation_suite_csv", suite_csv(default_mutation_cases()))
    suite_text = st.text_area("Suíte de testes (CSV)", key="mutation_suite_csv", height=220,
                              help="Colunas: id;p1;p2;p3;expected. Use NULL nas entradas e ponto ou vírgula decimal.")
    previous = st.session_state.get("mutation_result")
    # Preserve uma seleção anterior para explicar eventual rejeição após ampliar a suíte.
    options = [] if not previous or previous["source_digest"] != source_digest else [
        item["id"] for item in previous["analysis"].get("mutants", [])
        if item.get("status") in ("survived", "equivalent") or item["id"] in st.session_state.get("manual_equivalents", [])
    ]
    selected = st.multiselect("Mutantes equivalentes (revisão manual)", options, key="manual_equivalents")
    reason = st.text_input("Justificativa da equivalência", key="equivalence_reason")
    try:
        cases = parse_suite(suite_text)
    except ValueError as exc:
        cases = None
        st.error(str(exc))
    signature = _digest(_json({"suite": suite_text, "equivalents": selected, "reason": reason}))
    if st.button("Executar suíte e mutantes", key="run_mutation", type="primary", disabled=cases is None):
        if selected and not reason.strip():
            st.error("Registre a justificativa antes de excluir equivalentes do denominador.")
        else:
            try:
                result = run_mutation_analysis(source, cases, manual_equivalents={name: reason.strip() for name in selected})
                st.session_state["mutation_result"] = {
                    "source_digest": source_digest, "suite_digest": signature,
                    "source": source, "source_name": st.session_state["source_name"],
                    "analysis": result, "cases": cases, "equivalence_reason": reason.strip(),
                    "created_at": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds"),
                }
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    saved = st.session_state.get("mutation_result")
    if not saved:
        return None
    stale = saved["source_digest"] != source_digest or saved["suite_digest"] != signature
    if stale:
        st.warning("Fonte, suíte ou revisão de equivalência alterados: execute novamente. O resultado abaixo corresponde à execução anterior.")
    result = saved["analysis"]
    st.caption(f"Execução local: {saved['created_at']} · SHA-256: {saved['source_digest']}")
    if not result.get("supported", False):
        st.error("Mutação indisponível para este fonte: " + "; ".join(result.get("errors", [])))
    else:
        summary = result["summary"]
        if any(item.get("equivalence_rejected") for item in result.get("mutants", [])):
            st.warning("Uma equivalência declarada foi rejeitada porque a suíte distingue o mutante do original. Esse mutante continua contado como morto.")
        if not summary.get("suite_valid", True):
            st.warning(f"O original falhou em {summary['oracle_failures']} caso(s) contra o esperado. O escore considera apenas os {summary['eligible_cases']} casos aprovados pelo original; revise o oráculo antes de concluir sobre a suíte.")
        columns = st.columns(4)
        for column, label, key in zip(columns, ["Mortos", "Sobreviventes", "Inválidos", "Equivalentes declarados"],
                                      ["killed", "survived", "invalid", "equivalent"]):
            column.metric(label, summary[key])
        st.markdown("**MS = mortos / (total − inválidos − equivalentes)**")
        score = summary.get("score")
        st.write("Escore: não calculável nesta execução." if score is None else f"Escore: {score:.2%}")
        st.caption(result.get("model_scope", "Modelo local restrito."))
        st.markdown("**Resultados do original contra o oráculo informado**")
        _table(result.get("original_results", []))
        st.markdown("**Mutantes e testes que os distinguiram**")
        statuses = {"killed": "Morto", "survived": "Sobrevivente", "invalid": "Inválido", "equivalent": "Equivalente declarado"}
        _table([{"ID": item["id"], "Operador": item["operator"], "Status": statuses.get(item["status"], item["status"]),
                 "Linha": item["line"], "Antes": item["before"], "Depois": item["after"],
                 "Morto pelos casos": ", ".join(item.get("killed_by", []))} for item in result.get("mutants", [])])
        if result.get("mutants"):
            name = st.selectbox("Inspecionar mutante", [item["id"] for item in result["mutants"]], key="inspect_mutant")
            mutant = next(item for item in result["mutants"] if item["id"] == name)
            st.caption(mutant["description"])
            if mutant.get("error"):
                st.error(mutant["error"])
            _table(mutant.get("results", []))
            st.download_button("Baixar fonte mutante (.4gl)", mutant["source"], f"cad0001_{name}.4gl", key="download_mutant_source")
    st.download_button("Baixar evidências de mutação (.json)", _json(saved), "mutacao_cad0001.json", "application/json", key="download_mutation")
    return None if stale else saved


def _assisted_report(sprint: int, source: str, mode: str, api_key: str, model: str, evidence: dict) -> None:
    key = f"sprint_{sprint}_gemini"
    signature = _digest(_json(evidence))
    if mode != "Auditoria com Gemini":
        st.caption("O relatório local e as evidências estão disponíveis sem API. Selecione Auditoria com Gemini para um comentário assistido.")
    elif st.button("Gerar análise com Gemini", key=f"run_sprint_{sprint}_gemini"):
        try:
            with st.spinner("Comentando as evidências calculadas…"):
                report = generate_sprint_report(source, api_key.strip(), model.strip(), sprint, evidence)
            st.session_state[key] = {
                "report": report, "evidence_digest": signature, "source_digest": _digest(source),
                "model": model.strip(), "created_at": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds"),
            }
        except AuditServiceError as exc:
            st.error(str(exc))
    saved = st.session_state.get(key)
    if saved:
        if saved["evidence_digest"] != signature:
            st.warning("As evidências mudaram após o comentário do Gemini. Gere novamente para atualizá-lo.")
        st.caption(f"Gemini · {saved['model']} · {saved['created_at']} · SHA-256 {saved['source_digest']}")
        st.markdown(saved["report"], unsafe_allow_html=False)
        st.download_button("Baixar comentário Gemini (.md)",
                           f"Modelo: {saved['model']}\n\nGerado em: {saved['created_at']}\n\nSHA-256: {saved['source_digest']}\n\n{saved['report']}",
                           f"sprint{ sprint }_gemini.md", key=f"download_sprint_{sprint}_gemini")


def render_structural_sprint(sprint: int, mode: str, api_key: str, model: str, restore_source, import_upload) -> None:
    st.markdown(f'<div class="eyebrow">LABORATÓRIO / ANÁLISE ESTRUTURAL <span>SPRINT {sprint:02d}</span></div>', unsafe_allow_html=True)
    st.title("Caixa-branca e complexidade" if sprint == 2 else "Fluxo de dados e mutação")
    st.caption("Base: TestingStudio_Web_Kickoff.pptx, módulos 2 e 3, e aulas fornecidas em Downloads.")
    source = _editor(restore_source, import_upload)
    try:
        validate_source(source)
        analysis = analyze_source(source)
    except ValueError as exc:
        st.error(str(exc))
        return
    if not analysis["functions"]:
        st.error("Nenhuma função reconhecida neste fonte.")
        return
    function = _function_picker(analysis, sprint)
    for warning in function.get("limitations", []):
        st.caption(warning)
    mutation = None
    if not function["supported"]:
        st.error("Função não suportada: " + "; ".join(function["errors"]))
    elif sprint == 2:
        _control_flow(function)
    else:
        data, mutants = st.tabs(["Definições e usos", "Mutação e escore"])
        with data:
            st.subheader("Pares Def-Uso")
            st.caption("c-use: uso em cálculo/retorno. p-use: uso em predicado, associado a sua aresta. Uma redefinição interrompe o caminho da definição anterior.")
            if not function.get("def_use_complete", True):
                st.warning("O limite de pares foi atingido; esta tabela é parcial. Consulte as limitações no relatório.")
            _table(function["def_use"])
            st.markdown("**Anomalias e pontos de revisão**")
            _table(function["anomalies"])
            with st.expander("Nós de referência"):
                _table(function["nodes"])
        with mutants:
            mutation = _mutation(source, analysis["source_sha256"])
    st.divider()
    st.subheader("Relatório e evidências")
    report = local_report(sprint, analysis, mutation, st.session_state["source_name"])
    st.download_button("Baixar relatório local (.md)", report, f"sprint{sprint}_cad0001.md", "text/markdown; charset=utf-8", key=f"download_sprint_{sprint}_report")
    st.download_button("Baixar análise estrutural (.json)", _json({**analysis, "source": source, "source_name": st.session_state["source_name"]}), f"sprint{sprint}_estrutura.json", "application/json", key=f"download_sprint_{sprint}_json")
    with st.expander("Relatório local"):
        st.markdown(report, unsafe_allow_html=False)
    _assisted_report(sprint, source, mode, api_key, model, {"structural": analysis, "mutation": mutation})
    st.caption("Referências e roteiro de validação: docs/material-base.md e docs/sprints-2-3.md no projeto.")
