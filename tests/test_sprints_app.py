"""Exercise structural sprints through Streamlit, with all API access mocked."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from streamlit.runtime.memory_media_file_storage import MemoryMediaFileStorage
from streamlit.testing.v1 import AppTest

import gemini_service
import sprint_views
from audit import load_source


ROOT = Path(__file__).resolve().parents[1]
SOURCE = load_source(ROOT / "cad0001_item_calculo.txt")
SPRINT_2 = "Sprint 2 · Caixa-branca"
SPRINT_3 = "Sprint 3 · Fluxo de dados e mutação"


@pytest.fixture
def api_calls(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    generation = Mock(side_effect=AssertionError("Unexpected structural Gemini request"))
    discovery = Mock(side_effect=AssertionError("Unexpected model discovery"))
    monkeypatch.setattr(gemini_service, "generate_sprint_report", generation)
    monkeypatch.setattr(sprint_views, "generate_sprint_report", generation)
    monkeypatch.setattr(gemini_service, "generate_report", Mock(side_effect=AssertionError("Unexpected sprint 1 request")))
    monkeypatch.setattr(gemini_service, "list_available_models", discovery)
    monkeypatch.setattr(gemini_service.genai, "Client", Mock(side_effect=AssertionError("Unexpected network client")))
    return generation, discovery


@pytest.fixture
def app(api_calls):
    application = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20)
    application.secrets["GEMINI_API_KEY"] = ""
    application.run()
    assert not application.exception
    return application


@pytest.fixture
def downloads(monkeypatch):
    captured = {}
    original = MemoryMediaFileStorage.load_and_get_id

    def capture(self, path_or_data, mimetype, kind, filename=None):
        if filename:
            captured[filename] = path_or_data
        return original(self, path_or_data, mimetype, kind, filename)

    monkeypatch.setattr(MemoryMediaFileStorage, "load_and_get_id", capture)
    return captured


def select_calculation(application, sprint=2):
    application.selectbox(key="active_sprint").select(SPRINT_2 if sprint == 2 else SPRINT_3).run()
    assert not application.exception
    application.selectbox(key=f"structural_function_{sprint}").select("cad0001_calcula_valor").run()
    assert not application.exception


def metric(application, label):
    return next(item.value for item in application.metric if item.label == label)


def test_navigation_calculates_original_cfg_and_does_not_call_api(app, api_calls):
    assert app.selectbox(key="active_sprint").options == ["Sprint 1 · Caixa-preta", SPRINT_2, SPRINT_3, "Sprint 4 · Pitch e validação"]
    select_calculation(app)
    assert metric(app, "V(G) = E − N + 2") == "4"
    assert metric(app, "Decisões") == "3"
    assert app.text_area(key="source_editor").value == SOURCE
    assert len(app.get("graphviz_chart")) == 1

    app.text_input(key="gemini_api_key").set_value("fake-ui-key").run()
    select_calculation(app, 3)
    assert any("Pares Def-Uso" == item.value for item in app.subheader)
    assert app.dataframe
    assert "mutation_result" not in app.session_state
    app.run()
    for request in api_calls:
        request.assert_not_called()


def test_source_edits_remain_shared_across_all_sprint_navigation(app):
    edited = SOURCE.replace("    IF p_val3 IS NULL THEN LET p_val3 = 0 END IF", "")
    app.text_area(key="source_editor").set_value(edited).run()
    select_calculation(app)
    assert app.text_area(key="source_editor").value == edited
    assert metric(app, "V(G) = E − N + 2") == "3"
    select_calculation(app, 3)
    assert app.text_area(key="source_editor").value == edited
    app.selectbox(key="active_sprint").select("Sprint 1 · Caixa-preta").run()
    assert not app.exception
    assert app.text_area(key="source_editor").value == edited
    app.button(key="restore_source").click().run()
    assert not app.exception
    assert app.text_area(key="source_editor").value == SOURCE


def test_editing_source_recomputes_cfg_and_export_digest(app, downloads):
    select_calculation(app)
    original_json = json.loads(downloads["sprint2_estrutura.json"].decode("utf-8"))
    assert original_json["source_sha256"] == sha256(SOURCE.encode("utf-8")).hexdigest()

    edited = SOURCE.replace("    IF p_val3 IS NULL THEN LET p_val3 = 0 END IF", "")
    assert edited != SOURCE
    app.text_area(key="source_editor").set_value(edited).run()

    assert not app.exception
    assert metric(app, "V(G) = E − N + 2") == "3"
    digest = sha256(edited.encode("utf-8")).hexdigest()
    exported = json.loads(downloads["sprint2_estrutura.json"].decode("utf-8"))
    assert exported["source_sha256"] == digest
    report = downloads["sprint2_cad0001.md"].decode("utf-8")
    assert digest in report
    assert "V(G)=3" in report
    assert "SQL e Informix-4GL não foram executados" in report
    assert b"digraph" in downloads["cad0001_calcula_valor.dot"]


def test_mutation_requires_click_and_preserves_old_evidence_when_suite_changes(app, downloads, api_calls):
    select_calculation(app, 3)
    assert "mutation_result" not in app.session_state
    app.button(key="run_mutation").click().run()
    assert not app.exception
    saved = deepcopy(app.session_state["mutation_result"])
    assert saved["analysis"]["supported"]
    assert saved["analysis"]["summary"]["killed"] > 0
    assert saved["analysis"]["original_results"]
    evidence = downloads["mutacao_cad0001.json"]
    assert json.loads(evidence.decode("utf-8"))["source_digest"] == sha256(SOURCE.encode("utf-8")).hexdigest()

    app.text_area(key="mutation_suite_csv").set_value("id;p1;p2;p3;expected\nnovo;2;3;4;10\n").run()
    assert not app.exception
    assert any("execute novamente" in item.value for item in app.warning)
    assert app.session_state["mutation_result"] == saved
    assert downloads["mutacao_cad0001.json"] == evidence
    assert "## Mutação no modelo local" not in downloads["sprint3_cad0001.md"].decode("utf-8")
    for request in api_calls:
        request.assert_not_called()


def test_gemini_needs_click_renders_html_as_text_and_keeps_result_on_error(app, monkeypatch, downloads, api_calls):
    select_calculation(app)
    generation = api_calls[0]
    generation.side_effect = None
    report = '# Revisão\n\n<script>alert("teste")</script>'
    generation.return_value = report
    app.text_input(key="gemini_api_key").set_value("fake-ui-key").run()
    generation.assert_not_called()

    app.button(key="run_sprint_2_gemini").click().run()
    assert not app.exception
    generation.assert_called_once()
    args = generation.call_args.args
    assert args[:4] == (SOURCE, "fake-ui-key", "gemini-3.8-flash", 2)
    assert args[4]["structural"]["source_sha256"] == sha256(SOURCE.encode("utf-8")).hexdigest()
    rendered = next(item for item in app.markdown if item.value == report)
    assert not rendered.proto.allow_html
    saved = deepcopy(app.session_state["sprint_2_gemini"])
    downloaded = downloads["sprint2_gemini.md"]
    assert saved["source_digest"] in downloaded.decode("utf-8")

    generation.side_effect = gemini_service.AuditServiceError("Gemini temporariamente indisponível.")
    app.button(key="run_sprint_2_gemini").click().run()
    assert not app.exception
    assert any("temporariamente indisponível" in item.value for item in app.error)
    assert app.session_state["sprint_2_gemini"] == saved
    assert downloads["sprint2_gemini.md"] == downloaded


def test_csv_accepts_null_inputs_decimal_comma_and_quoted_ids():
    cases = sprint_views.parse_suite('id;p1;p2;p3;expected\n"caso; nulo"; NuLl ;1,25;-2,50;-2,50\n')
    assert cases == [{"id": "caso; nulo", "inputs": [None, "1.25", "-2.50"], "expected": "-2.50"}]
    assert sprint_views.parse_suite(sprint_views.suite_csv(cases)) == cases


@pytest.mark.parametrize("csv_text,message", [
    ("id,p1,p2,p3,expected\na,1,2,3,5\n", "cabeçalho"),
    ("id;p1;p2;p3;expected\n", "pelo menos"),
    ("id;p1;p2;p3;expected\na;1;2;3;5\n a ;1;2;3;5\n", "repetido"),
    ("id;p1;p2;p3;expected\na;1;2;3\n", "cinco colunas"),
    ("id;p1;p2;p3;expected\na;1;2;3;5;extra\n", "cinco colunas"),
    ("id;p1;p2;p3;expected\na;1; ;3;5\n", "cinco colunas"),
    ("id;p1;p2;p3;expected\n ;1;2;3;5\n", "cinco colunas"),
    ("id;p1;p2;p3;expected\n" + "a" * 100_000, "100.000"),
    ("id;p1;p2;p3;expected\n" + "".join(f"T{i};1;2;3;5\n" for i in range(101)), "100 casos"),
], ids=["wrong-delimiter", "empty", "duplicate-id", "missing-column", "extra-column", "empty-input", "empty-id", "oversized", "too-many-cases"])
def test_csv_rejects_ambiguous_or_oversized_suites(csv_text, message):
    with pytest.raises(ValueError, match=message):
        sprint_views.parse_suite(csv_text)
