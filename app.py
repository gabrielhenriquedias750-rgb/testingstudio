"""TestingStudio Web: laboratório de testes do CAD0001."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st

from audit import (
    boundary_rows,
    build_local_report,
    equivalence_rows,
    generate_cases,
    load_source,
    validate_source,
)
from gemini_service import AuditServiceError, DEFAULT_MODEL, generate_report, list_available_models


ROOT = Path(__file__).resolve().parent
SOURCE_PATH = ROOT / "cad0001_item_calculo.txt"

st.set_page_config(
    page_title="TestingStudio Web · CAD0001",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="auto",
)
st.markdown(f"<style>{(ROOT / 'assets' / 'styles.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def configured_key() -> str:
    """A chave permanece no ambiente/segredo ou na sessão do navegador."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    try:
        return str(st.secrets.get("GEMINI_API_KEY", ""))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return ""


def import_upload() -> None:
    uploaded = st.session_state.get("source_upload")
    if uploaded is None:
        return
    raw = uploaded.getvalue()
    if len(raw) > 100_000:
        st.session_state["upload_error"] = "O fonte deve ter no máximo 100 KB."
        return
    try:
        try:
            source = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            source = raw.decode("cp1252")
        validate_source(source)
    except (ValueError, UnicodeError) as exc:
        st.session_state["upload_error"] = str(exc)
        return
    st.session_state["source_editor"] = source
    st.session_state["source_name"] = uploaded.name
    st.session_state.pop("upload_error", None)


def restore_source() -> None:
    try:
        st.session_state["source_editor"] = load_source(SOURCE_PATH)
        st.session_state["source_name"] = SOURCE_PATH.name
        st.session_state.pop("upload_error", None)
    except (OSError, ValueError) as exc:
        st.session_state["upload_error"] = f"Não foi possível ler o TXT original: {exc}"


def clear_available_models() -> None:
    """A lista consultada pertence exclusivamente à chave desta sessão."""
    st.session_state.pop("available_models", None)
    st.session_state.pop("discovered_model", None)


def select_discovered_model() -> None:
    choice = st.session_state.get("discovered_model")
    if choice in st.session_state.get("available_models", []):
        st.session_state["gemini_model"] = choice


if "source_editor" not in st.session_state:
    restore_source()
    st.session_state.setdefault("source_editor", "")
    st.session_state.setdefault("source_name", "Fonte não carregado")

# Atualiza o antigo padrão inclusive nas sessões abertas antes desta correção.
# Um identificador personalizado informado pelo usuário continua selecionado.
if not st.session_state.get("current_model_default_applied"):
    if st.session_state.get("gemini_model") == "gemini-2.5-flash":
        st.session_state["gemini_model"] = DEFAULT_MODEL
    st.session_state["current_model_default_applied"] = True
st.session_state.setdefault("gemini_model", DEFAULT_MODEL)

with st.sidebar:
    st.markdown('<div class="brand">TestingStudio<small>CAD0001 · Teste de Software</small></div>', unsafe_allow_html=True)
    sprint = st.selectbox("Sprint", ["Sprint 1 · Caixa-preta", "Sprint 2 · Caixa-branca", "Sprint 3 · Fluxo de dados e mutação", "Sprint 4 · Pitch e validação"], key="active_sprint")
    sprint_number = int(sprint[7])
    st.caption(f"CAD0001 · Sprint {sprint_number}")
    st.divider()
    st.subheader("Conexão com Gemini")
    st.caption("Configure a análise assistida pelo Google AI Studio.")
    api_key = st.text_input("Gemini API Key", value=configured_key(), type="password", key="gemini_api_key", placeholder="Cole sua chave aqui", on_change=clear_available_models)
    if api_key.strip():
        st.caption("● Chave informada · conexão ainda não verificada")
    else:
        st.caption("○ Aguardando chave da API")
    st.link_button("Obter chave no Google AI Studio ↗", "https://aistudio.google.com/apikey", width="stretch")
    mode = st.radio("Modo de análise", ["Auditoria com Gemini", "Preparação local (sem API)"], key="analysis_mode")
    with st.expander("Configuração do modelo"):
        if st.button("Consultar modelos da chave", key="list_models", disabled=not api_key.strip(), width="stretch"):
            clear_available_models()
            try:
                with st.spinner("Consultando modelos de texto…"):
                    available = list_available_models(api_key.strip())
                st.session_state["available_models"] = available
                if st.session_state["gemini_model"] not in available:
                    st.session_state["gemini_model"] = available[0]
            except AuditServiceError as exc:
                st.error(str(exc))
        if st.session_state.get("available_models"):
            st.selectbox(
                "Modelos de texto retornados pela API",
                st.session_state["available_models"],
                index=None,
                placeholder="Selecione um modelo",
                key="discovered_model",
                on_change=select_discovered_model,
            )
            st.caption("Lista consultada para esta chave. A geração ainda depende de acesso ao modelo e cota.")
        model = st.text_input("Modelo Gemini", key="gemini_model")
        st.caption("O modelo 2.5 do manual tem acesso restrito pelo Google. Use o padrão atual ou consulte e selecione outro modelo da sua chave.")
    if mode == "Auditoria com Gemini":
        st.caption("Ao executar, o fonte exibido será enviado ao Gemini. A chave não é gravada nos arquivos do projeto.")
    else:
        st.caption("Gera tabelas, casos esperados e observações estáticas, sem enviar dados à API.")
    st.divider()
    with st.expander("Sobre o projeto"):
        st.markdown("**Teste de Software I**  \nProf. Frank Piffer  \nEmenta 62371 · 2026.2")
        st.caption("Caixa-preta · Caixa-branca · Fluxo de dados · Mutação")

if sprint_number == 4:
    from sprint4_view import render_delivery_sprint

    render_delivery_sprint(restore_source, import_upload)
    st.stop()

if sprint_number != 1:
    from sprint_views import render_structural_sprint

    render_structural_sprint(sprint_number, mode, api_key, model, restore_source, import_upload)
    st.stop()

st.markdown('<div class="eyebrow">LABORATÓRIO / AUDITORIA FUNCIONAL <span>SPRINT 01</span></div>', unsafe_allow_html=True)
st.title("Auditoria do CAD0001")
st.markdown('<p class="page-intro">Explore classes de entrada. Investigue fronteiras. Transforme regras em casos de teste.</p>', unsafe_allow_html=True)

st.caption("CAD0001 · PCE + AVL · ε = 0,01 · On, Off, Interior e Exterior")

with st.container():
    st.subheader("Código-fonte")
    st.caption("O TXT original foi carregado do projeto. Você pode editá-lo ou importar uma versão para comparar.")
    st.text_area("Fonte CAD0001", key="source_editor", height=340, max_chars=100_000, label_visibility="collapsed")
    left, right = st.columns([2, 1])
    with left:
        st.caption(f"Arquivo: {st.session_state['source_name']} · {len(st.session_state['source_editor'].splitlines())} linhas")
    with right:
        st.button("Restaurar TXT original", key="restore_source", on_click=restore_source, width="stretch")
    with st.expander("Importar outro fonte (.txt ou .4gl)"):
        st.file_uploader("Arquivo CAD0001", type=["txt", "4gl"], key="source_upload", on_change=import_upload)
        st.caption("Até 100 KB. A importação atualiza apenas o editor desta sessão.")
    if st.session_state.get("upload_error"):
        st.error(st.session_state["upload_error"])
    run_audit = st.button(
        "Executar auditoria de caixa-preta" if mode == "Auditoria com Gemini" else "Gerar relatório local",
        type="primary",
        width="stretch",
        key="run_audit",
        icon=":material/play_arrow:",
    )
with st.expander("Regras e critérios de teste"):
    st.markdown('<div class="method-card"><span class="method-tag">REGRA DE CÁLCULO</span><p class="formula">(p₁ × p₂) + p₃</p><p>Três parâmetros do tipo <code>DECIMAL(12,2)</code> determinam o valor calculado do item.</p></div>', unsafe_allow_html=True)
    st.markdown("**PCE · Classes de equivalência**  \nValores ≥ 0,00 são válidos. Negativos e nulos formam classes inválidas segundo o enunciado.")
    st.markdown("**AVL · Fronteira em zero**  \nTeste 0,00 e −0,01 com ε = 0,01, além dos pontos interior e exterior.")
    st.info("O manual classifica nulos como inválidos, mas seu exemplo os converte em zero. O TXT original também faz essa conversão e não rejeita negativos.", icon=":material/info:")

source = st.session_state["source_editor"]
source_digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
if run_audit:
    try:
        validate_source(source)
        if mode == "Auditoria com Gemini":
            if not api_key.strip():
                raise AuditServiceError("Insira sua Gemini API Key na barra lateral para executar a auditoria com IA. Para trabalhar sem chave, selecione Preparação local.")
            with st.spinner("Analisando classes e fronteiras com Gemini…"):
                report = generate_report(source, api_key.strip(), model.strip())
            report_kind = "Gemini"
        else:
            report = build_local_report(source)
            report_kind = "Local · sem IA"
        st.session_state["audit_result"] = {
            "report": report,
            "kind": report_kind,
            "model": model.strip() if report_kind == "Gemini" else None,
            "source_digest": source_digest,
            "source_name": st.session_state["source_name"],
            "created_at": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds"),
        }
        st.success("Relatório gerado. Explore a análise, as fronteiras e os casos abaixo.")
    except (ValueError, AuditServiceError) as exc:
        st.error(str(exc))

st.subheader("Resultados da auditoria")
result = st.session_state.get("audit_result")
stale = bool(result and result["source_digest"] != source_digest)
if stale:
    st.warning("O código-fonte foi alterado após a última análise. Execute novamente para atualizar o relatório.")

report_tab, chart_tab, cases_tab = st.tabs(["Relatório (PCE & AVL)", "Gráfico de fronteira", "Casos de teste"])
with report_tab:
    if result:
        st.caption(f"ANÁLISE {result['kind'].upper()} · {result['created_at']} · {result['source_name']}")
        st.markdown(result["report"], unsafe_allow_html=False)
        report_file = (
            f"# TestingStudio Web — CAD0001\n\n"
            f"Origem: {result['kind']}\n\n"
            f"Modelo: {result['model'] or 'não se aplica'}\n\n"
            f"Gerado em: {result['created_at']}\n\n"
            f"Arquivo: {result['source_name']}\n\n"
            f"SHA-256 do fonte: `{result['source_digest']}`\n\n---\n\n"
            f"{result['report']}\n"
        )
        st.download_button("Baixar relatório (.md)", report_file, "auditoria_cad0001.md", "text/markdown; charset=utf-8", key="download_report")
    else:
        st.info("Execute a auditoria para gerar o relatório. A matriz de classes e o plano de fronteiras já estão disponíveis para consulta.")
    with st.expander("Matriz PCE de referência", expanded=not bool(result)):
        st.caption("Oráculo do enunciado, independente da implementação. Nulos exigem esclarecimento devido à divergência com o exemplo.")
        st.dataframe(pd.DataFrame(equivalence_rows()), hide_index=True, width="stretch")

with chart_tab:
    st.subheader("Onde a regra muda de comportamento")
    st.caption("Fronteira inferior: 0,00 · ε = 0,01 porque DECIMAL(12,2) representa duas casas decimais.")
    frame = pd.DataFrame(boundary_rows())
    frame["Região"] = frame["Valor"].map(lambda value: "Inválida" if value < 0 else "Válida")
    chart = (
        alt.Chart(frame)
        .mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5, size=62)
        .encode(
            x=alt.X("Ponto:N", sort=frame["Ponto"].tolist(), title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Valor:Q", title="Valor de entrada (R$)"),
            color=alt.Color("Região:N", scale=alt.Scale(domain=["Válida", "Inválida"], range=["#0d9488", "#d87960"]), legend=alt.Legend(orient="top", title=None)),
            tooltip=[alt.Tooltip("Ponto:N"), alt.Tooltip("Valor:Q", format=".2f"), alt.Tooltip("Resultado esperado:N")],
        )
    )
    zero_data = pd.DataFrame({"zero": [0]})
    zero = alt.Chart(zero_data).mark_rule(color="#64748b", strokeDash=[4, 4]).encode(y="zero:Q")
    st.altair_chart((chart + zero).properties(height=300), width="stretch")
    st.markdown("**Um centavo faz a diferença.** O gráfico completo comprime a vizinhança do zero. Use esta ampliação para inspecionar On e Off:")
    near = frame.loc[frame["Valor"].abs() <= 0.01].copy()
    near_chart = alt.Chart(near).mark_circle(size=220).encode(
        x=alt.X("Valor:Q", scale=alt.Scale(domain=[-0.015, 0.005]), axis=alt.Axis(format=".2f"), title="Entrada próxima da fronteira"),
        y=alt.Y("Ponto:N", title=None),
        color=alt.Color("Região:N", scale=alt.Scale(domain=["Válida", "Inválida"], range=["#0d9488", "#d87960"]), legend=None),
        tooltip=[alt.Tooltip("Ponto:N"), alt.Tooltip("Valor:Q", format=".2f")],
    )
    near_zero = alt.Chart(zero_data).mark_rule(color="#64748b", strokeDash=[4, 4]).encode(x="zero:Q")
    st.altair_chart((near_chart + near_zero).properties(height=130), width="stretch")
    display_frame = frame.drop(columns="Região").copy()
    display_frame["Valor"] = display_frame["Valor"].map(lambda number: f"{number:.2f}".replace(".", ","))
    st.dataframe(display_frame, hide_index=True, width="stretch")

with cases_tab:
    st.subheader("Uma entrada por vez, uma hipótese por teste")
    st.caption("15 casos esperados: quatro pontos de fronteira e NULL para cada parâmetro. Base: (1,00; 1,00; 0,00). Os demais parâmetros permanecem válidos.")
    st.info("Este é um plano de teste com resultados esperados pelo enunciado. A aplicação não executa Informix-4GL e não apresenta esses valores como resultados observados.")
    cases = pd.DataFrame(generate_cases())
    parameter = st.selectbox("Filtrar por parâmetro", ["Todos", "val_param1", "val_param2", "val_param3"], key="case_parameter")
    visible = cases if parameter == "Todos" else cases.loc[cases["Parâmetro"] == parameter]
    st.dataframe(visible, hide_index=True, width="stretch")
    st.download_button("Exportar casos (.csv)", visible.to_csv(index=False, sep=";").encode("utf-8-sig"), "casos_cad0001.csv", "text/csv; charset=utf-8", key="download_cases")

st.divider()
st.caption("TestingStudio Web · Sprint 1 · Teste de Software I · PCE & AVL com ε = 0,01")
