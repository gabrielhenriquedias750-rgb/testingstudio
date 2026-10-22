"""Exercise the real Streamlit interface without a browser or API requests."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from unittest.mock import Mock

import pytest
from streamlit.runtime.memory_media_file_storage import MemoryMediaFileStorage
from streamlit.testing.v1 import AppTest

import gemini_service
from audit import load_source


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
SOURCE_PATH = ROOT / "cad0001_item_calculo.txt"
LOCAL_MODE = "Preparação local (sem API)"


@pytest.fixture(autouse=True)
def api_calls(monkeypatch):
    # A developer's configured key must never cause a real Gemini request.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    forbidden_request = Mock(side_effect=AssertionError("Unexpected Gemini request"))
    forbidden_discovery = Mock(side_effect=AssertionError("Unexpected model discovery request"))
    monkeypatch.setattr(gemini_service, "generate_report", forbidden_request)
    monkeypatch.setattr(gemini_service, "list_available_models", forbidden_discovery)
    return forbidden_request, forbidden_discovery


@pytest.fixture
def app(api_calls):
    application = AppTest.from_file(str(APP_PATH), default_timeout=15)
    application.secrets["GEMINI_API_KEY"] = ""
    application.run()
    assert not application.exception
    return application, api_calls[0]


@pytest.fixture
def downloads(monkeypatch):
    """Capture the bytes actually handed to Streamlit's download storage."""
    captured = {}
    original = MemoryMediaFileStorage.load_and_get_id

    def capture(self, path_or_data, mimetype, kind, filename=None):
        if filename:
            captured[filename] = path_or_data
        return original(self, path_or_data, mimetype, kind, filename)

    monkeypatch.setattr(MemoryMediaFileStorage, "load_and_get_id", capture)
    return captured


def test_initial_screen_loads_real_source_and_all_three_tabs(app):
    application, request = app

    assert application.text_area(key="source_editor").value == load_source(SOURCE_PATH)
    assert [tab.label for tab in application.tabs] == [
        "Relatório (PCE & AVL)", "Gráfico de fronteira", "Casos de teste"
    ]
    assert len(application.get("vega_lite_chart")) == 2
    assert [frame.value.shape[0] for frame in application.dataframe] == [9, 4, 15]
    assert application.text_input(key="gemini_model").value == "gemini-3.8-flash"
    assert application.button(key="list_models").disabled
    assert "audit_result" not in application.session_state
    request.assert_not_called()


def test_audit_without_key_explains_required_key_and_does_not_call_api(app):
    application, request = app

    application.button(key="run_audit").click().run()

    assert not application.exception
    assert any("Insira sua Gemini API Key" in message.value for message in application.error)
    assert "audit_result" not in application.session_state
    request.assert_not_called()


def test_local_report_persists_and_download_keeps_original_analysis(app, downloads):
    application, request = app
    original_source = application.text_area(key="source_editor").value
    original_digest = sha256(original_source.encode("utf-8")).hexdigest()

    application.radio(key="analysis_mode").set_value(LOCAL_MODE).run()
    application.button(key="run_audit").click().run()

    assert not application.exception
    result = dict(application.session_state["audit_result"])
    assert result["kind"] == "Local · sem IA"
    assert result["source_digest"] == original_digest
    assert "0,01" in result["report"]
    report_bytes = downloads["auditoria_cad0001.md"]
    assert original_digest in report_bytes.decode("utf-8")
    assert result["report"] in report_bytes.decode("utf-8")

    edited_source = original_source + "\n# Alteração posterior para revisão\n"
    edited_digest = sha256(edited_source.encode("utf-8")).hexdigest()
    application.text_area(key="source_editor").set_value(edited_source).run()

    assert not application.exception
    assert any("alterado após a última análise" in message.value for message in application.warning)
    assert dict(application.session_state["audit_result"]) == result
    assert downloads["auditoria_cad0001.md"] == report_bytes
    assert edited_digest not in downloads["auditoria_cad0001.md"].decode("utf-8")

    application.button(key="restore_source").click().run()

    assert not application.exception
    assert application.text_area(key="source_editor").value == original_source
    assert not application.warning
    assert dict(application.session_state["audit_result"]) == result
    request.assert_not_called()


@pytest.mark.parametrize("parameter", ["val_param1", "val_param2", "val_param3"])
def test_case_filter_shows_five_cases_and_exports_only_selected_parameter(app, downloads, parameter):
    application, request = app

    application.selectbox(key="case_parameter").select(parameter).run()

    assert not application.exception
    visible = application.dataframe[-1].value
    assert len(visible) == 5
    assert set(visible["Parâmetro"]) == {parameter}
    csv = downloads["casos_cad0001.csv"].decode("utf-8-sig")
    assert len(csv.splitlines()) == 6
    assert all(parameter in line for line in csv.splitlines()[1:])
    request.assert_not_called()


def test_mocked_gemini_report_survives_rerun_filter_and_download(app, monkeypatch, downloads):
    application, forbidden_request = app
    report = "## Relatório de integração simulado\n\nPCE e AVL com ε = 0,01."
    request = Mock(return_value=report)
    monkeypatch.setattr(gemini_service, "generate_report", request)
    source = application.text_area(key="source_editor").value

    application.text_input(key="gemini_api_key").set_value("fake-test-key").run()
    application.button(key="run_audit").click().run()

    assert not application.exception
    request.assert_called_once_with(source, "fake-test-key", "gemini-3.8-flash")
    result = dict(application.session_state["audit_result"])
    assert result["kind"] == "Gemini"
    assert result["report"] == report
    assert report in downloads["auditoria_cad0001.md"].decode("utf-8")
    assert "fake-test-key" not in downloads["auditoria_cad0001.md"].decode("utf-8")

    application.selectbox(key="case_parameter").select("val_param2").run()
    application.download_button(key="download_report").click().run()
    application.run()

    assert not application.exception
    assert dict(application.session_state["audit_result"]) == result
    assert len(application.dataframe[-1].value) == 5
    assert any(message.value == report for message in application.markdown)
    request.assert_called_once()
    forbidden_request.assert_not_called()


def test_model_discovery_requires_click_and_does_not_generate_report(app, api_calls, monkeypatch):
    application, generation = app
    discovery = Mock(return_value=["gemini-available-first", "gemini-available-second"])
    monkeypatch.setattr(gemini_service, "list_available_models", discovery)

    application.text_input(key="gemini_api_key").set_value("fake-discovery-key").run()

    assert not application.exception
    assert not application.button(key="list_models").disabled
    discovery.assert_not_called()

    application.button(key="list_models").click().run()

    assert not application.exception
    discovery.assert_called_once_with("fake-discovery-key")
    assert application.selectbox(key="discovered_model").options == [
        "gemini-available-first", "gemini-available-second"
    ]
    assert application.selectbox(key="discovered_model").value is None
    assert application.text_input(key="gemini_model").value == "gemini-available-first"
    assert "audit_result" not in application.session_state
    assert not application.success
    assert any("acesso ao modelo e cota" in message.value for message in application.caption)
    generation.assert_not_called()

    application.selectbox(key="case_parameter").select("val_param1").run()
    application.run()

    assert not application.exception
    assert application.session_state["available_models"] == [
        "gemini-available-first", "gemini-available-second"
    ]
    discovery.assert_called_once()
    generation.assert_not_called()
    api_calls[1].assert_not_called()


def test_selected_discovered_model_is_used_by_next_audit(app, monkeypatch):
    application, forbidden_generation = app
    discovery = Mock(return_value=["gemini-3.8-flash", "gemini-another-text-model"])
    generation = Mock(return_value="## Relatório do modelo selecionado")
    monkeypatch.setattr(gemini_service, "list_available_models", discovery)
    monkeypatch.setattr(gemini_service, "generate_report", generation)

    application.text_input(key="gemini_api_key").set_value("fake-select-key").run()
    application.button(key="list_models").click().run()

    assert not application.exception
    assert application.text_input(key="gemini_model").value == "gemini-3.8-flash"
    generation.assert_not_called()

    application.selectbox(key="discovered_model").select("gemini-another-text-model").run()

    assert not application.exception
    assert application.text_input(key="gemini_model").value == "gemini-another-text-model"
    generation.assert_not_called()

    application.button(key="run_audit").click().run()

    assert not application.exception
    generation.assert_called_once_with(
        load_source(SOURCE_PATH), "fake-select-key", "gemini-another-text-model"
    )
    assert application.session_state["audit_result"]["model"] == "gemini-another-text-model"
    application.run()
    assert not application.exception
    discovery.assert_called_once()
    generation.assert_called_once()
    forbidden_generation.assert_not_called()


def test_changing_api_key_clears_discovered_models_without_request(app, monkeypatch):
    application, generation = app
    discovery = Mock(return_value=["gemini-first", "gemini-second"])
    monkeypatch.setattr(gemini_service, "list_available_models", discovery)

    application.text_input(key="gemini_api_key").set_value("fake-first-key").run()
    application.button(key="list_models").click().run()
    application.selectbox(key="discovered_model").select("gemini-second").run()

    assert not application.exception
    assert application.session_state["available_models"] == ["gemini-first", "gemini-second"]
    assert application.session_state["discovered_model"] == "gemini-second"

    application.text_input(key="gemini_api_key").set_value("fake-other-key").run()

    assert not application.exception
    assert "available_models" not in application.session_state
    assert "discovered_model" not in application.session_state
    assert all(widget.key != "discovered_model" for widget in application.selectbox)
    discovery.assert_called_once_with("fake-first-key")
    generation.assert_not_called()


def test_failed_model_discovery_preserves_report_without_success_claim(app, monkeypatch):
    application, generation = app
    application.radio(key="analysis_mode").set_value(LOCAL_MODE).run()
    application.button(key="run_audit").click().run()
    saved_result = dict(application.session_state["audit_result"])
    discovery = Mock(side_effect=gemini_service.AuditServiceError("Não foi possível consultar modelos."))
    monkeypatch.setattr(gemini_service, "list_available_models", discovery)

    application.text_input(key="gemini_api_key").set_value("fake-unavailable-key").run()
    application.button(key="list_models").click().run()

    assert not application.exception
    assert any("Não foi possível consultar modelos" in message.value for message in application.error)
    assert not application.success
    assert "available_models" not in application.session_state
    assert dict(application.session_state["audit_result"]) == saved_result
    discovery.assert_called_once_with("fake-unavailable-key")
    generation.assert_not_called()


@pytest.mark.parametrize(
    ("saved_model", "expected_model"),
    [("gemini-2.5-flash", "gemini-3.8-flash"), ("gemini-custom", "gemini-custom")],
)
def test_session_model_migration_updates_old_default_and_preserves_custom(api_calls, saved_model, expected_model):
    application = AppTest.from_file(str(APP_PATH), default_timeout=15)
    application.secrets["GEMINI_API_KEY"] = ""
    application.session_state["gemini_model"] = saved_model

    application.run()

    assert not application.exception
    assert application.text_input(key="gemini_model").value == expected_model
    assert application.session_state["current_model_default_applied"]

    # An intentional choice after migration is preserved, even if it is the old identifier.
    application.text_input(key="gemini_model").set_value("gemini-2.5-flash").run()
    application.run()

    assert not application.exception
    assert application.text_input(key="gemini_model").value == "gemini-2.5-flash"
    api_calls[0].assert_not_called()
    api_calls[1].assert_not_called()


def test_service_error_is_visible_and_keeps_previous_report(app, monkeypatch):
    application, forbidden_request = app
    application.radio(key="analysis_mode").set_value(LOCAL_MODE).run()
    application.button(key="run_audit").click().run()
    saved_result = dict(application.session_state["audit_result"])
    request = Mock(side_effect=gemini_service.AuditServiceError("Gemini indisponível. Tente novamente."))
    monkeypatch.setattr(gemini_service, "generate_report", request)

    application.radio(key="analysis_mode").set_value("Auditoria com Gemini").run()
    application.text_input(key="gemini_api_key").set_value("fake-test-key").run()
    application.button(key="run_audit").click().run()

    assert not application.exception
    assert any("Gemini indisponível" in message.value for message in application.error)
    assert dict(application.session_state["audit_result"]) == saved_result
    request.assert_called_once()
    forbidden_request.assert_not_called()
