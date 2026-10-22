"""Pitch, verificações técnicas e registro de aceitação da entrega."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from delivery import acceptance_summary, acceptance_template, pitch_content, run_validation, validation_markdown
from audit import generate_cases
from presentation import delivery_bundle, json_text, pitch_html, pitch_markdown, table_csv
from sprint_views import _editor
from structural import default_mutation_cases


def _hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def _records(report: dict) -> list[dict]:
    saved = st.session_state.get("sprint4_acceptance", [])
    current = {item["id"]: item for item in saved if item.get("report_id") == report["report_id"] and item.get("source_sha256") == report["source_sha256"]}
    return [current.get(item["id"], item) for item in acceptance_template(report)]


def _pitch_panel(pitch: dict, current: bool) -> None:
    st.subheader("Apresente o valor do TestingStudio")
    st.caption("Proposta de apresentação em cerca de 4 minutos, adaptável ao tempo da disciplina. Público: estudantes, docentes e analistas que precisam inspecionar o CAD0001.")
    if not current:
        st.info("Execute a validação local para incluir métricas e resultados atuais no pitch.")
    names = [f"{index}. {slide['title']}" for index, slide in enumerate(pitch["slides"], 1)]
    selected = st.selectbox("Slide do pitch", names, key="sprint4_slide")
    slide = pitch["slides"][names.index(selected)]
    st.markdown(f"### {slide['title']}")
    for bullet in slide["bullets"]:
        st.markdown(f"- {bullet}", unsafe_allow_html=False)
    with st.expander(f"Fala sugerida · {slide['duration_seconds']} segundos"):
        st.write(slide["speaker_notes"])
    st.download_button("Baixar apresentação (.html)", pitch_html(pitch), "pitch_testingstudio.html", "text/html; charset=utf-8", key="sprint4_pitch_html")
    st.download_button("Baixar roteiro (.md)", pitch_markdown(pitch), "pitch_testingstudio.md", "text/markdown; charset=utf-8", key="sprint4_pitch_md")
    with st.expander("Demonstração sugerida"):
        st.markdown("1. Na sprint 1, mostre a fronteira 0,00 / −0,01 e a divergência do fonte.\n2. Na sprint 2, selecione o cálculo e explique V(G) e um desvio.\n3. Na sprint 3, acompanhe um par Def-Uso e um mutante distinguido pela suíte.\n4. Volte à sprint 4 e apresente evidências, limitações e os cenários de aceitação.")


def _technical_panel(report: dict | None) -> None:
    if not report:
        st.info("Clique em Executar validação local para gerar a matriz de rastreabilidade e as evidências.")
        return
    summary = report["summary"]
    functional = report.get("functional")
    if functional:
        result = functional["summary"]
        st.subheader("Validação funcional do CAD0001")
        st.write(f"**Resultado do programa auditado: {result['status']}.**")
        columns = st.columns(4)
        for column, label, key in zip(columns, ["PASS no plano", "FAIL no plano", "Pendentes no plano", "Executados no modelo"], ["passed", "failed", "pending", "executed"]):
            column.metric(label, result[key])
        st.caption("O plano normativo tem 15 casos. NULL permanece pendente de esclarecer o contrato; casos não selecionados continuam visíveis. A execução é do modelo local, sem runtime Informix.")
        st.markdown("**Requisito → casos planejados e resultados**")
        st.dataframe(pd.DataFrame(functional["requirements"]), hide_index=True, width="stretch")
        st.markdown("**Caso → requisitos, esperado e obtido**")
        test_rows = [{key: json_text(value) if isinstance(value, (dict, list)) else value for key, value in item.items()} for item in functional["tests"]]
        st.dataframe(pd.DataFrame(test_rows), hide_index=True, width="stretch")
        st.download_button("Baixar RTM funcional (.csv)", table_csv(functional["requirements"]).encode("utf-8-sig"), "rtm_funcional.csv", "text/csv; charset=utf-8", key="sprint4_functional_rtm")
        st.download_button("Baixar resultados funcionais (.csv)", table_csv(functional["tests"]).encode("utf-8-sig"), "casos_funcionais.csv", "text/csv; charset=utf-8", key="sprint4_functional_cases_csv")
        st.divider()
    st.subheader("Matriz de rastreabilidade e resultados")
    st.caption("As verificações abaixo avaliam a integridade técnica da ferramenta. Esse resultado é distinto da conformidade funcional do CAD0001 e da aceitação declarada pelo usuário.")
    columns = st.columns(4)
    for column, label, key in zip(columns, ["Aprovados", "Reprovados", "Pendentes", "Verificação técnica"], ["approved", "failed", "pending", "technical_status"]):
        column.metric(label, summary[key])
    st.caption(f"Execução: {report['created_at']} · Fonte: {report['source_name']} · SHA-256: {report['source_sha256']}")
    rows = [{key: json_text(value) if isinstance(value, (dict, list)) else value for key, value in item.items()} for item in report["checks"]]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    with st.expander("Evidências completas"):
        st.json(report, expanded=False)
    st.download_button("Baixar validação técnica (.json)", json_text(report), "validacao_testingstudio.json", "application/json", key="sprint4_validation_json")
    st.download_button("Baixar rastreabilidade (.csv)", table_csv(report["checks"]).encode("utf-8-sig"), "rastreabilidade_testingstudio.csv", "text/csv; charset=utf-8", key="sprint4_rtm_csv")


def _acceptance_panel(report: dict | None, current: bool, pitch: dict) -> None:
    st.subheader("Validação do uso com uma pessoa")
    st.caption("As verificações locais conferem o comportamento técnico. Os cenários abaixo registram se a ferramenta atende ao uso pretendido; começam pendentes e exigem avaliação explícita.")
    if not report or not current:
        st.info("Execute a validação do fonte atual antes de registrar aceitação ou preparar o pacote de entrega.")
        return
    records = _records(report)
    st.dataframe(pd.DataFrame([{"Cenário": item["id"], "Objetivo": item["objective"], "Estado": item["status"], "Responsável": item.get("reviewer", "")} for item in records]), hide_index=True, width="stretch")
    status = acceptance_summary(report, records)["status"]
    st.write(f"**Aceitação pelo usuário: {status}.**")
    identifier = st.selectbox("Cenário de aceitação", [item["id"] for item in records], key="sprint4_acceptance_case")
    case = next(item for item in records if item["id"] == identifier)
    st.markdown(f"**Objetivo:** {case['objective']}")
    st.write(f"Perfil: {case['profile']}")
    for index, step in enumerate(case["steps"] if isinstance(case["steps"], list) else [case["steps"]], 1):
        st.write(f"{index}. {step}")
    st.write(f"Resultado esperado: {case['expected']}")
    context = f"{report['report_id'][:12]}_{identifier}"
    with st.form(f"sprint4_acceptance_form_{context}"):
        states = ["Pendente", "Aprovado", "Reprovado"]
        decision = st.selectbox("Resultado da avaliação", states, index=states.index(case["status"]), key=f"sprint4_decision_{context}")
        reviewer = st.text_input("Responsável pela avaliação", value=case.get("reviewer", ""), key=f"sprint4_reviewer_{context}")
        observed = st.text_area("Resultado observado e evidência", value=case.get("observed", ""), key=f"sprint4_observed_{context}")
        save = st.form_submit_button("Registrar avaliação", key="sprint4_save_acceptance")
    if save:
        if decision != "Pendente" and (not reviewer.strip() or not observed.strip()):
            st.error("Informe responsável e resultado observado para aprovar ou reprovar este cenário.")
        else:
            record = {**case, "status": decision, "reviewer": reviewer.strip(), "observed": observed.strip(),
                      "executed_at": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")}
            history = st.session_state.get("sprint4_acceptance", [])
            st.session_state["sprint4_acceptance"] = history + [record]
            st.rerun()
    st.download_button("Baixar relatório de entrega (.md)", validation_markdown(report, records), "entrega_testingstudio.md", "text/markdown; charset=utf-8", key="sprint4_delivery_md")
    st.download_button("Baixar pacote de entrega (.zip)", delivery_bundle(report, pitch, records), "testingstudio_sprint4.zip", "application/zip", key="sprint4_delivery_zip")
    st.caption("O pacote inclui o fonte analisado, a suíte e as evidências em JSON, a matriz CSV, os registros de aceitação e o pitch offline. Ele preserva as pendências registradas.")


def render_delivery_sprint(restore_source, import_upload) -> None:
    st.markdown('<div class="eyebrow">LABORATÓRIO / ENTREGA <span>SPRINT 04</span></div>', unsafe_allow_html=True)
    st.title("Pitch e validação")
    st.caption("Apresente o problema, demonstre a solução e sustente as conclusões com evidências.")
    with st.expander("Base desta entrega"):
        st.markdown("Não foi encontrado enunciado específico da sprint 4 nos documentos conferidos. Esta proposta foi preparada a pedido com referências do [Sebrae sobre pitch](https://blog.rn.sebrae.com.br/pitch/) e da [NASA sobre validação](https://www.nasa.gov/reference/5-4-product-validation/). Tempo, cenários e critérios podem ser ajustados à disciplina.")
    source = _editor(restore_source, import_upload)
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    previous_mutation = st.session_state.get("mutation_result")
    has_suite = bool(previous_mutation and previous_mutation["source_digest"] == digest)
    if not has_suite:
        st.session_state["sprint4_use_suite"] = False
    use_suite = st.checkbox("Usar a suíte da última execução da Sprint 3", disabled=not has_suite, key="sprint4_use_suite")
    cases = previous_mutation["cases"] if use_suite and has_suite else default_mutation_cases()
    plan = generate_cases()
    all_ids = [item["ID"] for item in plan]
    selection = st.multiselect("Casos do plano funcional", all_ids, default=all_ids, key="sprint4_functional_cases",
                               help="A seleção executa casos da regra escrita da sprint 1. Os demais permanecem pendentes no plano completo.")
    signature = _hash({"source": source, "cases": cases, "functional_cases": sorted(selection)})
    st.caption(f"{len(cases)} casos selecionados. As verificações e o pitch funcionam sem API; a aceitação com usuário é registrada separadamente.")
    if st.button("Executar validação local", type="primary", key="sprint4_run_validation"):
        try:
            with st.spinner("Conferindo o fonte, os caminhos, os pares Def-Uso e a suíte…"):
                report = run_validation(source, st.session_state["source_name"], cases, selected_functional_ids=selection)
            st.session_state["sprint4_validation"] = report
            st.session_state["sprint4_validation_input"] = signature
        except ValueError as exc:
            st.error(str(exc))
    report = st.session_state.get("sprint4_validation")
    current = bool(report and report["source_sha256"] == digest and st.session_state.get("sprint4_validation_input") == signature)
    if report and not current:
        st.warning("Fonte ou suíte alterados após a validação. O relatório anterior está preservado; execute novamente para atualizar o pitch e a entrega.")
    pitch = pitch_content(report if current else None, _records(report) if current else ())
    pitch_tab, validation_tab, acceptance_tab = st.tabs(["Pitch e demonstração", "Validação técnica", "Aceitação e entrega"])
    with pitch_tab:
        _pitch_panel(pitch, current)
    with validation_tab:
        _technical_panel(report)
    with acceptance_tab:
        _acceptance_panel(report, current, pitch)
