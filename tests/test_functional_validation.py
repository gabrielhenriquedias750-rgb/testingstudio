"""Functional outcomes use the written oracle rather than code characterization."""

from pathlib import Path

import pytest

from delivery import pitch_content, run_validation, validation_markdown
from functional_validation import validate_functional_plan


SOURCE = Path(__file__).resolve().parents[1].joinpath("cad0001_item_calculo.txt").read_text(encoding="utf-8")


def requirement(report, identifier):
    return next(row for row in report["requirements"] if row["id"] == identifier)


def test_supplied_source_has_six_pass_six_fail_three_pending():
    report = validate_functional_plan(SOURCE)
    assert report["summary"] == {"passed": 6, "failed": 6, "pending": 3, "executed": 15, "selected": 15, "total": 15, "status": "Reprovado"}
    assert requirement(report, "REQ-CAD01")["status"] == "Aprovado"
    assert requirement(report, "REQ-CAD02")["status"] == "Aprovado"
    assert requirement(report, "REQ-CAD03")["status"] == "Reprovado"
    assert requirement(report, "REQ-CAD03")["failed"] == 6
    assert requirement(report, "REQ-CAD04")["status"] == "Pendente"
    assert report["source_sha256"] and "modelo local" in report["scope"]


def test_null_observations_never_resolve_the_normative_oracle():
    report = validate_functional_plan(SOURCE)
    nulls = [row for row in report["tests"] if "REQ-CAD04" in row["requirements"]]
    assert len(nulls) == 3
    for row in nulls:
        assert row["expected"] == "A esclarecer"
        assert row["status"] == "Pendente" and row["executed"] is True
        assert row["actual"] is not None
        assert "Contrato de NULL a confirmar" in row["reason"]
    assert nulls[0]["actual"] == "0.00"


def test_traceability_is_bidirectional_without_missing_cases():
    report = validate_functional_plan(SOURCE)
    ids = {row["id"] for row in report["requirements"]}
    assert len(report["tests"]) == len({row["id"] for row in report["tests"]}) == 15
    for test in report["tests"]:
        assert test["requirements"] and set(test["requirements"]) <= ids
        for identifier in test["requirements"]:
            assert test["id"] in requirement(report, identifier)["planned_cases"]
    for req in report["requirements"]:
        inverse = [test["id"] for test in report["tests"] if req["id"] in test["requirements"]]
        assert req["planned_cases"] == inverse
        assert req["planned_count"] == req["passed"] + req["failed"] + req["pending"] == len(inverse)
    assert {row["flow"] for row in report["tests"]} == {"Principal", "Alternativo / limite", "Exceção"}
    assert all(row["flow"] == "Principal" for row in report["tests"] if "Interior" in row["scenario"])
    assert all(row["flow"] == "Alternativo / limite" for row in report["tests"] if "On-Point" in row["scenario"])
    assert all(row["flow"] == "Exceção" for row in report["tests"] if any(point in row["scenario"] for point in ("Off-Point", "Exterior", "Nulo")))


def test_empty_selection_retains_fifteen_pending_unexecuted_cases():
    report = validate_functional_plan(SOURCE, [])
    assert report["summary"]["status"] == "Sem execução"
    assert report["summary"]["executed"] == report["summary"]["passed"] == report["summary"]["failed"] == 0
    assert report["summary"]["pending"] == 15
    assert all(row["status"] == "Sem execução" for row in report["requirements"])
    for test in report["tests"]:
        assert test["status"] == "Pendente" and test["executed"] is False
        assert test["actual"] is None and test["reason"].startswith("Não executado")


def test_partial_selection_does_not_approve_unexecuted_requirement_obligations():
    report = validate_functional_plan(SOURCE, ["CT-01", "CT-06", "CT-11"])
    assert report["summary"]["passed"] == report["summary"]["executed"] == 3
    assert report["summary"]["pending"] == 12
    assert requirement(report, "REQ-CAD02")["status"] == "Aprovado"
    assert requirement(report, "REQ-CAD01")["status"] == "Pendente"
    assert requirement(report, "REQ-CAD03")["status"] == "Sem execução"
    assert report["summary"]["status"] == "Pendente"
    failed = validate_functional_plan(SOURCE, ["CT-02"])
    assert requirement(failed, "REQ-CAD03")["status"] == "Reprovado"
    assert failed["summary"]["status"] == "Reprovado"


@pytest.mark.parametrize("selected", [["CT-01", "CT-01"], ["CT-99"], "CT-01", [None], [["CT-01"]]])
def test_selection_rejects_duplicates_unknown_and_invalid_ids(selected):
    with pytest.raises(ValueError):
        validate_functional_plan(SOURCE, selected)


def test_source_change_to_negative_guard_updates_conformity_without_assuming_null_contract():
    guarded = SOURCE.replace("    RETURN l_val_calculado", "    IF p_val1 < 0 OR p_val2 < 0 OR p_val3 < 0 THEN RETURN -1 END IF\n    RETURN l_val_calculado")
    original = validate_functional_plan(SOURCE)
    changed = validate_functional_plan(guarded)
    assert changed["source_sha256"] != original["source_sha256"]
    assert changed["summary"]["passed"] == 12 and changed["summary"]["failed"] == 0
    assert requirement(changed, "REQ-CAD03")["status"] == "Aprovado"
    assert requirement(changed, "REQ-CAD04")["status"] == "Pendente"
    assert changed["summary"]["status"] == "Pendente"


def test_unsupported_model_and_runtime_errors_are_pending_not_false_pass():
    unsupported = SOURCE.replace("(p_val1 * p_val2) + p_val3", "external(p_val1)")
    report = validate_functional_plan(unsupported)
    assert report["summary"]["passed"] == report["summary"]["failed"] == report["summary"]["executed"] == 0
    assert report["summary"]["pending"] == 15
    assert report["model_error"]
    assert all(row["actual"] is None and "Não observável" in row["reason"] for row in report["tests"])
    divide_zero = SOURCE.replace("(p_val1 * p_val2) + p_val3", "(p_val1 * p_val2) / p_val3")
    attempt = validate_functional_plan(divide_zero, ["CT-01"])
    test = attempt["tests"][0]
    assert test["status"] == "Pendente" and test["actual"] is None
    assert test["executed"] is True and "sem resultado observável" in test["reason"]
    with pytest.raises(ValueError):
        validate_functional_plan("FUNCTION other()\nRETURN 0\nEND FUNCTION")


def test_delivery_preserves_technical_checks_and_separates_functional_verdict_in_exports():
    report = run_validation(SOURCE)
    assert len(report["checks"]) == 9
    assert report["summary"]["failed"] == 0
    assert report["functional"]["summary"]["status"] == "Reprovado"
    assert report["mutation"]["summary"]["score"] == 1
    assert report["functional"]["source_sha256"] == report["source_sha256"]
    exported = validation_markdown(report)
    assert "Conformidade funcional do CAD0001 — RTM" in exported
    assert "Rastreabilidade requisito → casos" in exported
    assert "Rastreabilidade caso → requisitos" in exported
    assert "REQ-CAD03" in exported and "CT-02" in exported
    pitch = pitch_content(report)
    evidence = " ".join(pitch["slides"][3]["bullets"])
    speech = pitch["slides"][3]["speaker_notes"]
    assert "Conformidade funcional CAD0001: Reprovado; 6 PASS, 6 FAIL e 3 pendentes" in evidence
    assert "6 casos passaram, 6 falharam e 3 ficaram pendentes" in speech
    assert "separados da suíte de caracterização" in speech
    empty = run_validation(SOURCE, selected_functional_ids=[])
    assert empty["functional"]["summary"]["status"] == "Sem execução"
    assert empty["functional"]["selection_sha256"] != report["functional"]["selection_sha256"]
    assert "0 PASS, 0 FAIL e 15 pendentes" in " ".join(pitch_content(empty)["slides"][3]["bullets"])
