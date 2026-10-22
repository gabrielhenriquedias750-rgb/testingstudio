"""Verify portable exports preserve evidence and keep untrusted text inert."""

from copy import deepcopy
import csv
from hashlib import sha256
import html
import io
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from audit import load_source
from delivery import acceptance_template, pitch_content, run_validation
from presentation import delivery_bundle, pitch_html, pitch_markdown, table_csv


ROOT = Path(__file__).resolve().parents[1]
SOURCE = load_source(ROOT / "cad0001_item_calculo.txt")


@pytest.fixture(scope="module")
def report():
    return run_validation(SOURCE, "cad0001_item_calculo.txt")


def test_html_escapes_untrusted_slide_titles_bullets_and_notes():
    payload = '<img src=x onerror="alert(1)"><script>alert("x")</script> & \'quoted\''
    pitch = pitch_content()
    pitch["slides"][0].update(title=payload, bullets=[payload], speaker_notes=payload)
    exported = pitch_html(pitch)
    assert exported.count(html.escape(payload, quote=True)) == 3
    assert payload not in exported
    assert "<img src=x" not in exported
    assert "<script>alert" not in exported
    assert '<html lang="pt-BR">' in exported


def test_html_is_offline_and_exposes_each_slide_and_navigation(report):
    pitch = pitch_content(report)
    exported = pitch_html(pitch)
    assert exported.count('<section class="slide"') == len(pitch["slides"])
    assert all(html.escape(slide["title"], quote=True) in exported for slide in pitch["slides"])
    assert "ArrowRight" in exported and "ArrowLeft" in exported
    assert "@media print" in exported
    assert "<script src=" not in exported
    assert '<link rel="stylesheet"' not in exported
    assert report["report_id"] in exported
    assert report["source_sha256"] in exported


@pytest.mark.parametrize("payload", ["=1+1", "+SUM(A1)", "-2+3", "@SUM(A1)", "\t=1+1", "\r=1+1"])
def test_csv_treats_spreadsheet_formulas_as_text(payload):
    exported = table_csv([{"id": "AC-01", "observed": payload, "reviewer": "Pessoa; avaliadora"}])
    rows = list(csv.DictReader(io.StringIO(exported), delimiter=";"))
    assert rows[0]["observed"] == "'" + payload
    assert rows[0]["reviewer"] == "Pessoa; avaliadora"


def test_csv_keeps_union_of_columns_and_nested_evidence():
    rows = [{"id": "A", "evidence": {"line": 44, "branch": "V"}}, {"id": "B", "observed": "linha 1\nlinha 2"}]
    exported = list(csv.DictReader(io.StringIO(table_csv(rows)), delimiter=";"))
    assert json.loads(exported[0]["evidence"]) == rows[0]["evidence"]
    assert exported[1]["observed"] == rows[1]["observed"]
    assert exported[0]["observed"] == exported[1]["evidence"] == ""


def test_bundle_is_self_contained_and_copies_exact_source_snapshot(report, tmp_path, monkeypatch):
    (tmp_path / "secrets.toml").write_text('GEMINI_API_KEY="must-not-be-bundled"', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    original = deepcopy(report)
    acceptance = acceptance_template(report)
    pitch = pitch_content(report)
    package = delivery_bundle(report, pitch, acceptance)
    with ZipFile(io.BytesIO(package)) as archive:
        assert set(archive.namelist()) == {
            "LEIA-ME.md", "fonte_analisado.4gl", "validacao.json", "validacao.md",
            "rastreabilidade.csv", "aceitacao.csv", "pitch.md", "pitch.html",
            "funcional_requisitos.csv", "funcional_casos.csv",
        }
        source = archive.read("fonte_analisado.4gl")
        assert source.decode("utf-8") == SOURCE
        assert sha256(source).hexdigest() == report["source_sha256"]
        evidence = json.loads(archive.read("validacao.json"))
        assert evidence["validation"] == report
        assert evidence["acceptance"] == acceptance
        assert all(case["status"] == "Pendente" for case in evidence["acceptance"])
        assert all(b"must-not-be-bundled" not in archive.read(name) for name in archive.namelist())
        assert report["source_sha256"] in archive.read("LEIA-ME.md").decode("utf-8")
    assert report == original


def test_bundle_escapes_spreadsheet_formulas_in_rtm_and_acceptance(report):
    validation = deepcopy(report)
    validation["checks"][0]["requirement"] = '=HYPERLINK("https://example.invalid")'
    validation["functional"]["requirements"][0]["description"] = "=untrusted requirement"
    validation["functional"]["tests"][0]["reason"] = "+untrusted observed reason"
    acceptance = acceptance_template(report)
    acceptance[0]["reviewer"] = "+untrusted reviewer"
    acceptance[0]["observed"] = "@SUM(A1)"
    with ZipFile(io.BytesIO(delivery_bundle(validation, pitch_content(validation), acceptance))) as archive:
        rtm = list(csv.DictReader(io.StringIO(archive.read("rastreabilidade.csv").decode("utf-8")), delimiter=";"))
        cases = list(csv.DictReader(io.StringIO(archive.read("aceitacao.csv").decode("utf-8")), delimiter=";"))
        functional_requirements = list(csv.DictReader(io.StringIO(archive.read("funcional_requisitos.csv").decode("utf-8")), delimiter=";"))
        functional_tests = list(csv.DictReader(io.StringIO(archive.read("funcional_casos.csv").decode("utf-8")), delimiter=";"))
    assert rtm[0]["requirement"] == "'" + validation["checks"][0]["requirement"]
    assert cases[0]["reviewer"] == "'+untrusted reviewer"
    assert cases[0]["observed"] == "'@SUM(A1)"
    assert functional_requirements[0]["description"] == "'=untrusted requirement"
    assert functional_tests[0]["reason"] == "'+untrusted observed reason"


def test_optional_junit_is_included_verbatim_only_when_supplied(report):
    junit = b'<?xml version="1.0"?><testsuites tests="1" failures="0"/>'
    with ZipFile(io.BytesIO(delivery_bundle(report, pitch_content(report), acceptance_template(report), junit=junit))) as archive:
        assert archive.read("pytest.xml") == junit


def test_markdown_pitch_preserves_all_notes_and_proposal_provenance(report):
    pitch = pitch_content(report)
    exported = pitch_markdown(pitch)
    assert all(slide["speaker_notes"] in exported for slide in pitch["slides"])
    assert report["report_id"] in exported
    assert report["source_sha256"] in exported
    assert "https://blog.rn.sebrae.com.br/pitch/" in exported
    assert "https://www.nasa.gov/reference/5-4-product-validation/" in exported


def test_html_escapes_untrusted_provenance_metadata():
    payload = '<img src=x onerror="alert(1)">'
    pitch = pitch_content()
    pitch.update(report_id=payload, source_sha256=payload)
    exported = pitch_html(pitch)
    assert payload not in exported
    assert html.escape(payload, quote=True) in exported
