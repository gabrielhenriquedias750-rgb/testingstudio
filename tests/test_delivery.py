"""Fresh local validation evidence and honest, pending manual acceptance."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

import delivery
from delivery import acceptance_summary, acceptance_template, pitch_content, run_validation, validation_markdown
from structural import default_mutation_cases


SOURCE = Path(__file__).resolve().parents[1].joinpath("cad0001_item_calculo.txt").read_text(encoding="utf-8")


def check(report, identifier):
    return next(row for row in report["checks"] if row["id"] == identifier)


def test_validation_computes_fresh_source_suite_and_evidence_without_acceptance():
    report = run_validation(SOURCE, "cad0001_item_calculo.txt")
    assert report["source"] == SOURCE
    assert report["source_sha256"] == sha256(SOURCE.encode("utf-8")).hexdigest()
    assert report["source_sha256"] == report["structural"]["source_sha256"] == report["mutation"]["source_sha256"]
    assert len(report["suite_sha256"]) == 64 and report["report_id"].startswith("VAL-")
    assert report["created_at"].endswith("-03:00")
    assert report["schema_version"] == "1.0"
    assert check(report, "S4-01")["status"] == "Aprovado"
    assert check(report, "S1-01")["observed"] == {"planned_cases": 15, "epsilon": "0.01", "executed_4gl_cases": 0, "classification": "Plano de testes"}
    for identifier in ("S2-01", "S2-02", "S3-01", "S3-02", "S3-03"):
        assert check(report, identifier)["status"] == "Aprovado", check(report, identifier)
    assert report["mutation"]["summary"]["killed"] == 12
    assert check(report, "S4-02")["status"] == "Pendente"
    assert report["summary"]["acceptance_status"] == "Pendente"
    assert report["summary"]["status"] == "Pendente"
    assert report["summary"]["failed"] == 0
    assert any("pytest" in limit for limit in report["limits"])


def test_source_and_suite_changes_recompute_provenance_and_observed_results():
    cases = default_mutation_cases()
    baseline = run_validation(SOURCE, cases=cases)
    changed = SOURCE.replace("    RETURN l_val_calculado", "    IF l_val_calculado < 0 THEN RETURN -1 END IF\n    RETURN l_val_calculado")
    newer = run_validation(changed, cases=cases)
    assert newer["source_sha256"] != baseline["source_sha256"]
    assert newer["report_id"] != baseline["report_id"]
    assert newer["suite_sha256"] == baseline["suite_sha256"]
    formula = next(row for row in newer["structural_summary"] if row["function"] == "cad0001_calcula_valor")
    assert formula["metrics"]["cyclomatic"] == 5
    assert check(newer, "S3-02")["status"] == "Reprovado"
    cases[0]["expected"] = "999"
    revised = run_validation(SOURCE, cases=cases)
    assert revised["suite_sha256"] != baseline["suite_sha256"]
    assert baseline["cases"][0]["expected"] == "10"
    assert revised["source_sha256"] == baseline["source_sha256"]


@pytest.mark.parametrize("source", ["", "FUNCTION f()\nRETURN 1\nEND FUNCTION", "FUNCTION cad0001_calcula_valor(a,b,c)\nRETURN 1"])
def test_invalid_source_raises_friendly_value_error(source):
    with pytest.raises(ValueError):
        run_validation(source)


def test_wrong_oracle_is_failed_and_no_eligible_score_is_invented():
    report = run_validation(SOURCE, cases=[{"id": "WRONG", "inputs": ["2", "3", "4"], "expected": "999"}])
    assert check(report, "S3-02")["status"] == "Reprovado"
    assert check(report, "S3-03")["status"] == "Pendente"
    assert report["mutation"]["summary"]["score"] is None
    assert report["summary"]["technical_status"] == "Reprovado"
    assert report["summary"]["acceptance_status"] == "Pendente"


def test_survivors_require_review_without_inventing_a_score_threshold():
    report = run_validation(SOURCE, cases=[{"id": "ZERO", "inputs": ["0", "0", "0"], "expected": "0"}])
    assert check(report, "S3-02")["status"] == "Aprovado"
    mutation = check(report, "S3-03")
    assert mutation["status"] == "Pendente"
    assert mutation["observed"]["accounting_consistent"] is True
    assert mutation["observed"]["score_recomputed"] == 0
    assert len(mutation["evidence"]["survivors"]) == 12
    assert "sem estabelecer escore mínimo" in mutation["method"]


def test_unknown_additional_function_prevents_claim_all_functions_verified():
    report = run_validation(SOURCE + "\nFUNCTION strange(x)\nWHILE x > 0\nLET x = x - 1\nEND WHILE\nEND FUNCTION\n")
    assert check(report, "S2-01")["status"] == "Reprovado"
    assert check(report, "S2-02")["status"] == "Reprovado"
    assert check(report, "S3-01")["status"] == "Reprovado"
    assert check(report, "S3-02")["status"] == "Aprovado"


def test_dataflow_undefined_use_is_an_evidenced_failure():
    report = run_validation(SOURCE + "\nFUNCTION uninitialized(p)\nDEFINE x INTEGER\nRETURN x\nEND FUNCTION\n")
    assert check(report, "S3-04")["status"] == "Reprovado"
    assert check(report, "S3-04")["observed"]["uses_without_definition"] == 1
    evidence = check(report, "S3-04")["evidence"]
    assert any(row["function"] == "uninitialized" and row["kind"] == "use-without-definition" and row["evidence_path"] for row in evidence)


def test_validation_independently_detects_corrupt_basis_and_du(monkeypatch):
    original = delivery.analyze_source
    def corrupted(source):
        data = original(source)
        formula = next(row for row in data["functions"] if row["name"] == "cad0001_calcula_valor")
        formula["basis_paths"][1] = deepcopy(formula["basis_paths"][0])
        pair = next(row for row in formula["def_use"] if row["use_type"] == "c-use" and row["variable"] == "p_val1")
        redefine = next(row["id"] for row in formula["nodes"] if row["kind"] == "let" and row["defs"] == ["p_val1"])
        pair["path"].insert(1, redefine)
        return data
    monkeypatch.setattr(delivery, "analyze_source", corrupted)
    report = run_validation(SOURCE)
    assert check(report, "S2-02")["status"] == "Reprovado"
    assert check(report, "S3-01")["status"] == "Reprovado"


def test_acceptance_templates_are_pending_editable_and_bound_to_the_run():
    report = run_validation(SOURCE)
    records = acceptance_template(report)
    assert len(records) == 6 and len({record["id"] for record in records}) == 6
    for record in records:
        assert record["status"] == "Pendente"
        assert record["observed"] == record["reviewer"] == record["executed_at"] == ""
        assert record["source_sha256"] == report["source_sha256"] and record["report_id"] == report["report_id"]
        assert record["steps"] and record["expected"] and record["profile"]
    records[0]["observed"] = "Observação manual do avaliador."
    assert acceptance_template(report)[0]["observed"] == ""
    assert all(record["report_id"] == "" for record in acceptance_template())


def test_markdown_exports_manual_claim_without_promoting_automatic_acceptance():
    report = run_validation(SOURCE)
    records = acceptance_template(report)
    records[0].update({"status": "Aprovado", "reviewer": "Avaliador", "observed": "Passos conferidos manualmente."})
    exported = validation_markdown(report, records)
    assert report["source_sha256"] in exported and report["suite_sha256"] in exported
    assert "Passos conferidos manualmente." in exported
    assert "nem concede homologação" in exported
    assert report["source"] in exported
    assert report["summary"]["acceptance_status"] == "Pendente"
    records[0]["report_id"] = "relatorio-antigo"
    assert "Ausente ou diferente" in validation_markdown(report, records)


def test_pitch_is_editable_four_minute_proposal_and_uses_only_fresh_numbers():
    draft = pitch_content()
    assert draft["proposal"] and draft["editable"] and draft["report_id"] is None
    assert len(draft["slides"]) == 6
    assert draft["duration_seconds"] == 240
    assert all({"title", "bullets", "speaker_notes", "duration_seconds"} <= slide.keys() for slide in draft["slides"])
    assert "Nenhuma execução" in " ".join(draft["slides"][3]["bullets"])
    report = run_validation(SOURCE, cases=[{"id": "ZERO", "inputs": ["0", "0", "0"], "expected": "0"}])
    pitch = pitch_content(report)
    evidence = " ".join(pitch["slides"][3]["bullets"])
    assert "0 mortos, 12 sobreviventes" in evidence
    assert "1/1 casos" in evidence
    assert report["report_id"] in evidence
    assert report["source_sha256"] == pitch["source_sha256"]
    assert "aceitação manual: Pendente" in evidence
    speech = pitch["slides"][3]["speaker_notes"]
    assert "0 foram mortos, 12 sobreviveram" in speech
    assert "aprovou 1 dos 1 casos" in speech
    assert "modelo local" in speech


def test_manual_summary_requires_known_current_signed_observations():
    report = run_validation(SOURCE)
    records = acceptance_template(report)
    for row in records:
        row.update(status="Aprovado", reviewer="Avaliador", observed="Cenário executado conforme registrado.")
    summary = acceptance_summary(report, records)
    assert summary["status"] == "Aprovado" and summary["approved"] == 6 and summary["pending"] == 0
    assert report["summary"]["acceptance_status"] == "Pendente"
    assert "aceitação manual: Aprovado (declaração manual)" in " ".join(pitch_content(report, records)["slides"][3]["bullets"])
    exported = validation_markdown(report, records)
    assert '"acceptance_status": "Pendente"' in exported  # Immutable initial snapshot.
    assert '"status": "Aprovado"' in exported  # Current signed manual declaration.
    assert "Estado atual da aceitação" in exported
    unsigned = deepcopy(records)
    unsigned[0]["reviewer"] = " "
    assert acceptance_summary(report, unsigned)["pending"] == 1
    unobserved = deepcopy(records)
    unobserved[0]["observed"] = ""
    assert acceptance_summary(report, unobserved)["status"] == "Pendente"
    stale = deepcopy(records)
    stale[0]["report_id"] = "anterior"
    assert acceptance_summary(report, stale)["status"] == "Pendente"
    mismatched = deepcopy(records)
    mismatched[0]["source_sha256"] = "fonte-anterior"
    assert acceptance_summary(report, mismatched)["pending"] == 1
    unknown = [{**records[0], "id": "AC-UNKNOWN"}]
    assert acceptance_summary(report, unknown)["approved"] == 0
    assert acceptance_summary(report, unknown)["unknown_records"] == 1
    assert acceptance_summary(report, records[:-1])["pending"] == 1


def test_latest_manual_record_wins_and_signed_rejection_is_not_hidden():
    report = run_validation(SOURCE)
    records = acceptance_template(report)
    for row in records:
        row.update(status="Aprovado", reviewer="Avaliador", observed="Observação registrada.")
    rejected = {**records[0], "status": "Reprovado", "observed": "A funcionalidade não atendeu ao cenário."}
    summary = acceptance_summary(report, records + [rejected])
    assert summary["status"] == "Reprovado" and summary["failed"] == 1
    stale_latest = {**records[0], "report_id": "anterior"}
    assert acceptance_summary(report, records + [stale_latest])["status"] == "Pendente"
    assert acceptance_summary(report, [rejected] + records)["status"] == "Aprovado"
    assert acceptance_summary(None, records)["status"] == "Pendente"
