"""Source-dependent CFG/DU evidence and executable local mutation scoring."""

from copy import deepcopy
from pathlib import Path

import pytest

import structural
from structural import analyze_source, cfg_dot, default_mutation_cases, run_mutation_analysis


SOURCE = Path(__file__).resolve().parents[1].joinpath("cad0001_item_calculo.txt").read_text(encoding="utf-8")


def function(source, name):
    return next(item for item in analyze_source(source)["functions"] if item["name"] == name)


def test_original_metrics_and_independent_executable_graph_paths():
    analysis = analyze_source(SOURCE)
    expected = {"cad0001_main": 1, "cad0001_calcula_valor": 4, "cad0001_incluir": 3, "cad0001_alterar": 3, "cad0001_excluir": 3}
    for item in analysis["functions"]:
        assert item["supported"], item["errors"]
        metrics = item["metrics"]
        assert metrics["cyclomatic"] == expected[item["name"]]
        assert metrics["cyclomatic"] == metrics["edges"] - metrics["nodes"] + 2
        assert metrics["cyclomatic"] == metrics["decisions"] + 1
        assert metrics["basis_rank"] == metrics["cyclomatic"]
        assert len(item["basis_paths"]) == metrics["cyclomatic"]
        edges = {edge["id"]: edge for edge in item["edges"]}
        for path in item["basis_paths"]:
            assert path["nodes"][0] == "n0" and path["nodes"][-1] == "n1"
            assert len(path["edges"]) == len(path["nodes"]) - 1
            for start, end, edge in zip(path["nodes"], path["nodes"][1:], path["edges"]):
                assert (edges[edge]["source"], edges[edge]["target"]) == (start, end)
        assert "digraph CFG" in cfg_dot(item)


def test_source_changes_drive_metrics_instead_of_fixed_template():
    changed = SOURCE.replace("    RETURN l_val_calculado", "    IF l_val_calculado < 0 THEN RETURN -1 END IF\n    RETURN l_val_calculado")
    original = function(SOURCE, "cad0001_calcula_valor")
    updated = function(changed, "cad0001_calcula_valor")
    assert original["metrics"]["cyclomatic"] == 4
    assert updated["metrics"]["cyclomatic"] == 5
    assert updated["metrics"]["basis_rank"] == 5
    assert analyze_source(SOURCE)["source_sha256"] != analyze_source(changed)["source_sha256"]


@pytest.mark.parametrize("statement", ["WHILE x > 0\nLET x = x - 1\nEND WHILE", "BOGUS x", "LET x = 1\nBOGUS x", "RETURN x\nBOGUS x"])
def test_unknown_syntax_is_explicitly_unsupported(statement):
    item = function(f"FUNCTION f(x)\n{statement}\nEND FUNCTION", "f")
    assert not item["supported"]
    assert item["errors"]
    assert item["nodes"] == [] and item["metrics"] is None
    with pytest.raises(ValueError):
        cfg_dot(item)


def test_inline_else_nested_if_and_quoted_control_words():
    source = '''FUNCTION f(p)
DEFINE x INTEGER
IF p > 0 THEN
  IF p > 2 THEN LET x = 3 ELSE LET x = 2 END IF
ELSE
  LET x = 1
END IF
MESSAGE "IF THEN ELSE END IF"
RETURN x
END FUNCTION'''
    item = function(source, "f")
    assert item["supported"], item["errors"]
    assert item["metrics"]["cyclomatic"] == 3
    assert not any(row["kind"] == "use-without-definition" for row in item["anomalies"])


def test_reaching_definitions_kill_and_predicate_uses_belong_to_edges():
    source = '''FUNCTION f(p)
DEFINE x INTEGER
LET x = p
LET x = 2
IF x > 0 THEN RETURN x ELSE RETURN 0 END IF
END FUNCTION'''
    item = function(source, "f")
    first, second = [node for node in item["nodes"] if node["kind"] == "let"]
    predicate = next(node for node in item["nodes"] if node["kind"] == "if")
    pairs = [row for row in item["def_use"] if row["variable"] == "x"]
    assert all(row["definition"] == second["id"] for row in pairs)
    puses = [row for row in pairs if row["use"] == predicate["id"]]
    assert {row["branch"] for row in puses} == {"V", "F"}
    assert all(row["use_type"] == "p-use" and row["edge"] for row in puses)
    assert any(row["kind"] == "definition-redefined-without-use" and row["evidence_path"] == [first["id"], second["id"]] for row in item["anomalies"])


def test_partial_definition_has_evidenced_undefined_path_not_false_certainty():
    source = "FUNCTION f(p)\nDEFINE x INTEGER\nIF p > 0 THEN LET x = 1 END IF\nRETURN x\nEND FUNCTION"
    item = function(source, "f")
    anomaly = next(row for row in item["anomalies"] if row["kind"] == "use-without-definition")
    assert anomaly["variable"] == "x"
    assert anomaly["evidence_path"][0] == "n0"
    assert any(row["variable"] == "x" for row in item["def_use"])


def test_initialize_null_is_definition_and_sql_status_has_virtual_definition():
    main = function(SOURCE, "cad0001_main")
    initialize = next(node for node in main["nodes"] if node["kind"] == "initialize")
    assert "mr_item.val_param1" in initialize["defs"]
    inclusion = function(SOURCE, "cad0001_incluir")
    inserts = {node["id"] for node in inclusion["nodes"] if node["kind"] == "insert"}
    status_uses = [row for row in inclusion["def_use"] if row["variable"] == "sqlca.sqlcode" and row["use_type"] == "p-use"]
    assert status_uses and all(row["definition"] in inserts for row in status_uses)


def test_return_has_unified_exit_and_unreachable_code_is_not_added_to_complexity():
    item = function("FUNCTION f(p)\nRETURN p\nIF p > 0 THEN RETURN 1 END IF\nEND FUNCTION", "f")
    assert item["supported"]
    assert item["metrics"]["cyclomatic"] == 1
    assert any("inalcançável" in warning for warning in item["limitations"])
    assert len([node for node in item["nodes"] if node["kind"] == "exit"]) == 1


def test_long_acyclic_function_does_not_enumerate_exponential_paths():
    source = "FUNCTION f(p)\n" + "\n".join(f"IF p > {n} THEN LET p = p + 1 END IF" for n in range(25)) + "\nRETURN p\nEND FUNCTION"
    item = function(source, "f")
    assert item["supported"]
    assert item["metrics"]["cyclomatic"] == 26
    assert item["metrics"]["basis_rank"] == 26


def test_graph_and_expression_limits_fail_explicitly():
    many_nodes = "FUNCTION f(p)\n" + "LET p = p + 1\n" * 510 + "RETURN p\nEND FUNCTION"
    item = function(many_nodes, "f")
    assert not item["supported"] and "500" in item["errors"][0]
    deep = "FUNCTION f(p)\nRETURN " + "(" * 80 + "p" + ")" * 80 + "\nEND FUNCTION"
    assert not function(deep, "f")["supported"]


def test_default_mutation_suite_runs_real_mutants_and_exact_score():
    result = run_mutation_analysis(SOURCE, default_mutation_cases())
    assert result["supported"], result["errors"]
    assert result["original_failures"] == []
    summary = result["summary"]
    assert summary["total"] == summary["valid"] == summary["killed"] == 12
    assert summary["score"] == 1 and summary["score_percent"] == 100
    assert summary["invalid"] == summary["equivalent"] == 0
    assert all(mutant["source"] != SOURCE and mutant["killed_by"] for mutant in result["mutants"])
    assert next(row for row in result["original_results"] if row["id"] == "M07")["actual"] == "3.00"
    assert next(row for row in result["original_results"] if row["id"] == "M08")["actual"] == "-2"


def test_weak_suite_survivors_are_not_automatically_equivalent():
    cases = [{"id": "ZERO", "p1": "0", "p2": "0", "p3": "0", "expected": "0"}]
    result = run_mutation_analysis(SOURCE, cases)
    assert result["summary"]["score"] == 0
    assert result["summary"]["survived"] == 12
    assert result["summary"]["equivalent"] == 0
    manual = run_mutation_analysis(SOURCE, cases, {"MU01": "Revisão manual específica do domínio restrito."})
    assert manual["summary"]["denominator"] == 11
    assert manual["summary"]["equivalent"] == 1
    assert manual["mutants"][0]["equivalence_proven"] is False
    contradicted = run_mutation_analysis(SOURCE, default_mutation_cases(), {"MU01": "suposição"})
    assert contradicted["mutants"][0]["status"] == "killed"
    assert "equivalence_rejected" in contradicted["mutants"][0]


def test_invalid_mutant_is_excluded_and_denominator_is_exact(monkeypatch):
    generate = structural._mutations
    def with_invalid(source, compiled):
        mutants = generate(source, compiled)
        invalid = deepcopy(mutants[0])
        invalid.update({"id": "BAD", "source": source.replace("RETURN l_val_calculado", "RETURN mystery()")})
        return mutants + [invalid]
    monkeypatch.setattr(structural, "_mutations", with_invalid)
    result = run_mutation_analysis(SOURCE, default_mutation_cases())
    summary = result["summary"]
    assert summary["total"] == 13 and summary["invalid"] == 1
    assert summary["valid"] == summary["denominator"] == 12
    assert summary["score"] == 1
    assert result["mutants"][-1]["status"] == "invalid"


def test_wrong_oracles_are_explicit_and_cannot_kill_mutants():
    cases = [{"id": "WRONG", "inputs": ["2", "3", "4"], "expected": "999"}]
    result = run_mutation_analysis(SOURCE, cases)
    assert len(result["original_failures"]) == 1
    assert result["summary"]["eligible_cases"] == 0
    assert result["summary"]["score"] is None
    assert result["summary"]["killed"] == 0
    assert not result["summary"]["suite_valid"]
    mixed = run_mutation_analysis(SOURCE, cases + default_mutation_cases()[:1])
    assert mixed["summary"]["eligible_cases"] == 1
    assert mixed["summary"]["oracle_failures"] == 1
    assert mixed["summary"]["score"] is not None


def test_model_follows_source_formula_and_supported_negative_guard():
    changed = SOURCE.replace("(p_val1 * p_val2) + p_val3", "(p_val1 * p_val2) - p_val3")
    result = run_mutation_analysis(changed, [{"id": "A", "inputs": ["2", "3", "4"], "expected": "2"}])
    assert result["original_results"][0]["actual"] == "2"
    assert not result["original_failures"]
    guarded = SOURCE.replace("    RETURN l_val_calculado", "    IF p_val1 < 0 OR p_val2 < 0 OR p_val3 < 0 THEN RETURN -1 END IF\n    RETURN l_val_calculado")
    guarded_result = run_mutation_analysis(guarded, [{"id": "N", "inputs": ["-2", "3", "4"], "expected": "-1"}])
    assert guarded_result["supported"] and guarded_result["original_results"][0]["passed"]
    assert any(mutant["operator"] == "ROR" for mutant in guarded_result["mutants"])


def test_model_refuses_external_calls_and_invalid_case_inputs():
    changed = SOURCE.replace("LET l_val_calculado = (p_val1 * p_val2) + p_val3", "LET l_val_calculado = arbitrary(p_val1)")
    assert not run_mutation_analysis(changed, default_mutation_cases())["supported"]
    assert not run_mutation_analysis(SOURCE, [{"id": "A", "p1": 1, "expected": 0}])["supported"]
    assert not run_mutation_analysis(SOURCE, [{"id": "A", "inputs": ["NaN", "0", "0"], "expected": 0}])["supported"]
    assert not run_mutation_analysis(SOURCE, [default_mutation_cases()[0]] * 2)["supported"]


def test_mutation_sites_ignore_operators_and_keywords_in_comments():
    annotated = SOURCE.replace(
        "(p_val1 * p_val2) + p_val3",
        "(p_val1 * p_val2) # explicar + - * / formula\n        + p_val3",
    ).replace(
        "IF p_val1 IS NULL THEN LET p_val1 = 0 END IF",
        "IF p_val1 IS NULL # THEN < >= = IS NOT NULL\n    THEN LET p_val1 = 0 # + - * /\n    END IF",
    )
    baseline = run_mutation_analysis(SOURCE, default_mutation_cases())
    result = run_mutation_analysis(annotated, default_mutation_cases())
    assert result["supported"], result["errors"]
    assert result["summary"]["total"] == baseline["summary"]["total"] == 12
    assert result["summary"]["killed"] == 12
    assert result["summary"]["score"] == 1
    assert [item["operator"] for item in result["mutants"]] == [item["operator"] for item in baseline["mutants"]]
    for mutant in result["mutants"]:
        if mutant["operator"] in {"AOR", "CRP"}:
            assert "# explicar + - * / formula" in mutant["source"]
            assert "# + - * /" in mutant["source"]


def test_record_field_definitions_are_case_insensitive():
    source = '''DEFINE REC RECORD
    X INTEGER
END RECORD
FUNCTION f()
INITIALIZE REC.* TO NULL
RETURN rec.x
END FUNCTION'''
    item = function(source, "f")
    assert item["supported"], item["errors"]
    initialize = next(node for node in item["nodes"] if node["kind"] == "initialize")
    returned = next(node for node in item["nodes"] if node["kind"] == "return")
    assert initialize["defs"] == ["rec.x"]
    assert returned["uses"] == ["rec.x"]
    pair = next(row for row in item["def_use"] if row["use"] == returned["id"])
    assert pair["definition"] == initialize["id"]
    assert pair["variable"] == "rec.x"


def test_select_into_keeps_old_destination_value_read_in_where():
    source = '''FUNCTION f(p)
SELECT col INTO p FROM tab WHERE col = p
RETURN p
END FUNCTION'''
    item = function(source, "f")
    assert item["supported"], item["errors"]
    selected = next(node for node in item["nodes"] if node["kind"] == "select")
    returned = next(node for node in item["nodes"] if node["kind"] == "return")
    assert selected["defs"] == ["p", "sqlca.sqlcode"]
    assert selected["uses"] == ["p"]
    assert any(row["variable"] == "p" and row["definition"] == "n0" and row["use"] == selected["id"] for row in item["def_use"])
    assert any(row["variable"] == "p" and row["definition"] == selected["id"] and row["use"] == returned["id"] for row in item["def_use"])
    no_read = function(source.replace("WHERE col = p", "WHERE col = 1"), "f")
    assert next(node for node in no_read["nodes"] if node["kind"] == "select")["uses"] == []
