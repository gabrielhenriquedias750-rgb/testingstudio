"""Exercise the delivery workflow and its exported snapshots without API access."""

from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
from streamlit.runtime.memory_media_file_storage import MemoryMediaFileStorage
from streamlit.testing.v1 import AppTest

import gemini_service
import sprint4_view
import sprint_views
from audit import generate_cases, load_source
from structural import default_mutation_cases


ROOT = Path(__file__).resolve().parents[1]
SOURCE = load_source(ROOT / "cad0001_item_calculo.txt")
SPRINT_4 = "Sprint 4 · Pitch e validação"


@pytest.fixture
def api_calls(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    requests = []
    for module, name in [
        (gemini_service, "generate_report"),
        (gemini_service, "generate_sprint_report"),
        (gemini_service, "list_available_models"),
        (sprint_views, "generate_sprint_report"),
        (gemini_service.genai, "Client"),
    ]:
        request = Mock(side_effect=AssertionError("Unexpected network request in delivery workflow"))
        monkeypatch.setattr(module, name, request)
        requests.append(request)
    return requests


@pytest.fixture
def app(api_calls):
    application = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20)
    application.secrets["GEMINI_API_KEY"] = ""
    application.run()
    application.selectbox(key="active_sprint").select(SPRINT_4).run()
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


def download_visible(application, label):
    return any(item.proto.label == label for item in application.get("download_button"))


def validate(application):
    application.button(key="sprint4_run_validation").click().run()
    assert not application.exception
    return deepcopy(application.session_state["sprint4_validation"])


def test_pitch_is_available_before_validation_without_api(app, downloads, api_calls):
    app.run()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == [
        "Pitch e demonstração", "Validação técnica", "Aceitação e entrega"
    ]
    assert app.text_area(key="source_editor").value == SOURCE
    assert "sprint4_validation" not in app.session_state
    assert len(app.selectbox(key="sprint4_slide").options) == 6
    assert "pitch_testingstudio.html" in downloads
    assert b"<!doctype html>" in downloads["pitch_testingstudio.html"]
    assert not download_visible(app, "Baixar pacote de entrega (.zip)")
    for request in api_calls:
        request.assert_not_called()


def test_validation_requires_click_and_exports_fresh_hash_suite_and_rtm(app, downloads, monkeypatch, api_calls):
    computation = Mock(wraps=sprint4_view.run_validation)
    monkeypatch.setattr(sprint4_view, "run_validation", computation)
    app.session_state["audit_result"] = {"report": "STALE_AUDIT_SENTINEL"}
    app.session_state["mutation_result"] = {
        "source_digest": "old-source", "cases": [], "analysis": {"summary": {"killed": 999}}
    }
    app.run()
    computation.assert_not_called()

    report = validate(app)
    computation.assert_called_once_with(SOURCE, "cad0001_item_calculo.txt", default_mutation_cases(),
                                        selected_functional_ids=[case["ID"] for case in generate_cases()])
    assert report["source"] == SOURCE
    digest = sha256(SOURCE.encode("utf-8")).hexdigest()
    assert report["source_sha256"] == report["structural"]["source_sha256"] == report["mutation"]["source_sha256"] == digest
    assert report["cases"] == default_mutation_cases()
    assert len(report["mutation"]["original_results"]) == len(report["cases"])
    assert report["mutation"]["summary"]["killed"] != 999
    exported = json.loads(downloads["validacao_testingstudio.json"].decode("utf-8"))
    assert exported == report
    rtm = downloads["rastreabilidade_testingstudio.csv"].decode("utf-8-sig")
    assert all(check["id"] in rtm and check["requirement"] in rtm for check in report["checks"])
    assert "STALE_AUDIT_SENTINEL" not in json.dumps(report)
    assert report["summary"]["acceptance_status"] == "Pendente"
    assert any(check["id"] == "S4-02" and check["status"] == "Pendente" for check in report["checks"])
    assert download_visible(app, "Baixar pacote de entrega (.zip)")
    for request in api_calls:
        request.assert_not_called()


def test_current_sprint3_suite_is_recomputed_for_delivery_and_changes_invalidate_it(app):
    cases = [{"id": "manual-one", "inputs": ["2", "3", "4"], "expected": "10"}]
    app.session_state["mutation_result"] = {
        "source_digest": sha256(SOURCE.encode("utf-8")).hexdigest(),
        "cases": cases, "analysis": {"summary": {"killed": 999}},
    }
    app.run()
    assert not app.checkbox(key="sprint4_use_suite").disabled
    app.checkbox(key="sprint4_use_suite").check().run()
    report = validate(app)
    assert report["cases"] == cases
    assert report["mutation"]["original_results"][0]["id"] == "manual-one"
    assert report["mutation"]["summary"]["killed"] != 999

    app.checkbox(key="sprint4_use_suite").uncheck().run()
    assert not app.exception
    assert any("suíte alterados" in warning.value for warning in app.warning)
    assert app.session_state["sprint4_validation"] == report
    assert not download_visible(app, "Baixar pacote de entrega (.zip)")


def test_manual_acceptance_needs_reviewer_and_observation_and_remains_scoped(app, downloads):
    report = validate(app)
    assert any("Aceitação pelo usuário: Pendente" in item.value for item in app.markdown)
    assert "sprint4_acceptance" not in app.session_state
    identifier = app.selectbox(key="sprint4_acceptance_case").value
    context = f"{report['report_id'][:12]}_{identifier}"
    decision = f"sprint4_decision_{context}"
    reviewer = f"sprint4_reviewer_{context}"
    observed = f"sprint4_observed_{context}"
    assert app.selectbox(key=decision).value == "Pendente"
    app.selectbox(key=decision).select("Aprovado")
    app.button(key="sprint4_save_acceptance").click().run()
    assert not app.exception
    assert any("Informe responsável" in message.value for message in app.error)
    assert "sprint4_acceptance" not in app.session_state

    app.text_input(key=reviewer).set_value("Avaliadora local")
    app.button(key="sprint4_save_acceptance").click().run()
    assert any("Informe responsável" in message.value for message in app.error)
    assert "sprint4_acceptance" not in app.session_state

    app.text_area(key=observed).set_value("Fonte e SHA-256 conferidos no pacote, no navegador local.")
    app.button(key="sprint4_save_acceptance").click().run()
    assert not app.exception
    saved = deepcopy(app.session_state["sprint4_acceptance"])
    assert len(saved) == 1
    assert saved[0]["status"] == "Aprovado"
    assert saved[0]["report_id"] == report["report_id"]
    assert saved[0]["source_sha256"] == report["source_sha256"]
    assert saved[0]["reviewer"] == "Avaliadora local"
    assert saved[0]["observed"].startswith("Fonte e SHA-256")
    assert any("Aceitação pelo usuário: Pendente" in item.value for item in app.markdown)

    with ZipFile(io.BytesIO(downloads["testingstudio_sprint4.zip"])) as archive:
        evidence = json.loads(archive.read("validacao.json"))
    approved = [case for case in evidence["acceptance"] if case["status"] == "Aprovado"]
    assert len(approved) == 1
    assert all(case["status"] == "Pendente" for case in evidence["acceptance"] if case["id"] != identifier)

    edited = SOURCE + "\n# Fonte revisada depois da avaliação\n"
    app.text_area(key="source_editor").set_value(edited).run()
    assert not app.exception
    assert any("Fonte ou suíte alterados" in warning.value for warning in app.warning)
    assert app.session_state["sprint4_acceptance"] == saved
    assert not download_visible(app, "Baixar pacote de entrega (.zip)")
    assert report["report_id"] not in downloads["pitch_testingstudio.html"].decode("utf-8")

    app.selectbox(key="active_sprint").select("Sprint 1 · Caixa-preta").run()
    assert not app.exception
    assert app.text_area(key="source_editor").value == edited

    app.selectbox(key="active_sprint").select(SPRINT_4).run()
    updated = validate(app)
    assert updated["report_id"] != report["report_id"]
    assert updated["source_sha256"] == sha256(edited.encode("utf-8")).hexdigest()
    with ZipFile(io.BytesIO(downloads["testingstudio_sprint4.zip"])) as archive:
        current_acceptance = json.loads(archive.read("validacao.json"))["acceptance"]
    assert all(case["status"] == "Pendente" and case["report_id"] == updated["report_id"] for case in current_acceptance)
    assert app.session_state["sprint4_acceptance"] == saved


def test_invalid_source_keeps_previous_validation_snapshot_and_hides_delivery(app, downloads):
    saved = validate(app)
    previous_json = downloads["validacao_testingstudio.json"]
    app.text_area(key="source_editor").set_value("").run()
    app.button(key="sprint4_run_validation").click().run()
    assert not app.exception
    assert app.error
    assert app.session_state["sprint4_validation"] == saved
    assert downloads["validacao_testingstudio.json"] == previous_json
    assert not download_visible(app, "Baixar pacote de entrega (.zip)")


def test_delivery_zip_contains_selected_source_hash_and_no_configured_key(app, downloads, api_calls):
    secret = "fake-private-key-must-not-be-exported"
    app.text_input(key="gemini_api_key").set_value(secret).run()
    edited = SOURCE + "\n# Snapshot da apresentação\n"
    app.text_area(key="source_editor").set_value(edited).run()
    report = validate(app)
    with ZipFile(io.BytesIO(downloads["testingstudio_sprint4.zip"])) as archive:
        assert archive.read("fonte_analisado.4gl").decode("utf-8") == edited
        assert report["source_sha256"] in archive.read("LEIA-ME.md").decode("utf-8")
        assert report["report_id"] in archive.read("pitch.html").decode("utf-8")
        assert all(secret.encode() not in archive.read(name) for name in archive.namelist())
        assert all("secret" not in name.lower() and ".streamlit" not in name for name in archive.namelist())
    for request in api_calls:
        request.assert_not_called()


def test_functional_plan_exports_full_bidirectional_matrix_separate_from_tool_checks(app, downloads):
    assert app.multiselect(key="sprint4_functional_cases").value == [case["ID"] for case in generate_cases()]
    report = validate(app)
    functional = report["functional"]
    summary = functional["summary"]
    assert {key: summary[key] for key in ("passed", "failed", "pending", "total", "executed")} == {
        "passed": 6, "failed": 6, "pending": 3, "total": 15, "executed": 15,
    }
    assert len(report["checks"]) == 9
    assert len(functional["tests"]) == 15
    assert len(functional["requirements"]) == 4
    visible_metrics = {item.label: item.value for item in app.metric}
    assert {key: visible_metrics[key] for key in ("PASS no plano", "FAIL no plano", "Pendentes no plano", "Executados no modelo")} == {
        "PASS no plano": "6", "FAIL no plano": "6", "Pendentes no plano": "3", "Executados no modelo": "15",
    }
    assert functional["source_sha256"] == report["source_sha256"]
    assert {case["id"] for case in functional["tests"]} == {case["ID"] for case in generate_cases()}
    requirements = {item["id"]: item for item in functional["requirements"]}
    assert set(requirements) == {"REQ-CAD01", "REQ-CAD02", "REQ-CAD03", "REQ-CAD04"}
    for case in functional["tests"]:
        assert case["requirements"]
        assert all(case["id"] in requirements[identifier]["planned_cases"] for identifier in case["requirements"])
    assert any(frame.value.shape[0] == 15 and "id" in frame.value.columns for frame in app.dataframe)
    with ZipFile(io.BytesIO(downloads["testingstudio_sprint4.zip"])) as archive:
        assert "funcional_requisitos.csv" in archive.namelist()
        assert "funcional_casos.csv" in archive.namelist()
        exported = json.loads(archive.read("validacao.json"))["validation"]["functional"]
        assert exported == functional


def test_empty_functional_selection_stays_pending_and_selection_changes_invalidate_export(app):
    original = validate(app)
    app.multiselect(key="sprint4_functional_cases").set_value([]).run()
    assert not app.exception
    assert app.session_state["sprint4_validation"] == original
    assert app.warning
    assert not download_visible(app, "Baixar pacote de entrega (.zip)")

    empty = validate(app)
    functional = empty["functional"]
    assert functional["summary"]["executed"] == 0
    assert functional["summary"]["pending"] == 15
    assert functional["summary"]["passed"] == functional["summary"]["failed"] == 0
    assert functional["summary"]["status"] == "Sem execução"
    assert all(case["status"] == "Pendente" and not case["selected"] and not case["executed"] for case in functional["tests"])
    assert all(requirement["status"] == "Sem execução" for requirement in functional["requirements"])
    assert download_visible(app, "Baixar pacote de entrega (.zip)")

    app.multiselect(key="sprint4_functional_cases").set_value(["CT-01"]).run()
    assert not app.exception
    assert app.session_state["sprint4_validation"] == empty
    assert not download_visible(app, "Baixar pacote de entrega (.zip)")
    partial = validate(app)["functional"]
    assert partial["summary"]["passed"] == partial["summary"]["executed"] == 1
    assert partial["summary"]["pending"] == 14
    assert partial["summary"]["status"] == "Pendente"
    formula = next(item for item in partial["requirements"] if item["id"] == "REQ-CAD01")
    assert formula["passed"] == 1
    assert formula["pending"] == formula["planned_count"] - 1
    assert formula["status"] == "Pendente"


def test_all_six_manual_approvals_update_pitch_without_rewriting_technical_snapshot(app, downloads):
    report = validate(app)
    identifiers = list(app.selectbox(key="sprint4_acceptance_case").options)
    assert len(identifiers) == 6
    for identifier in identifiers:
        app.selectbox(key="sprint4_acceptance_case").select(identifier).run()
        context = f"{report['report_id'][:12]}_{identifier}"
        app.selectbox(key=f"sprint4_decision_{context}").select("Aprovado")
        app.text_input(key=f"sprint4_reviewer_{context}").set_value("Avaliadora da sessão local")
        app.text_area(key=f"sprint4_observed_{context}").set_value(f"{identifier}: cenário observado no navegador local e evidência conferida.")
        app.button(key="sprint4_save_acceptance").click().run()
        assert not app.exception
    assert any("Aceitação pelo usuário: Aprovado" in item.value for item in app.markdown)
    assert app.session_state["sprint4_validation"] == report
    assert report["summary"]["acceptance_status"] == "Pendente"
    pitch = downloads["pitch_testingstudio.md"].decode("utf-8")
    assert "aceitação manual: Aprovado" in pitch
    assert "declaração manual" in pitch
    assert report["source_sha256"] in pitch
    with ZipFile(io.BytesIO(downloads["testingstudio_sprint4.zip"])) as archive:
        evidence = json.loads(archive.read("validacao.json"))
        assert evidence["validation"] == report
        assert all(case["status"] == "Aprovado" for case in evidence["acceptance"])
        assert "aceitação manual: Aprovado" in archive.read("pitch.md").decode("utf-8")
