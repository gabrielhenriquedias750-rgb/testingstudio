"""Functional RTM for the existing 15-case PCE/AVL plan.

The written plan supplies the oracle. The current source supplies observed
results through structural.py's restricted Decimal model. NULL's written
oracle is unresolved, so observing zero never makes a NULL case pass.

The four private helpers imported below deliberately reuse the same bounded
model as mutation analysis; no 4GL, SQL, shell, eval or external code is run.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json

from audit import PARAMETERS, generate_cases, validate_source
from structural import UnsupportedSyntax, _compile_model, _decimal, _execute_model, _result_text


REQUIREMENTS = (
    ("REQ-CAD01", "Aplicar (p1 × p2) + p3 para entradas válidas, não negativas."),
    ("REQ-CAD02", "Aceitar zero na fronteira válida e aplicar a fórmula."),
    ("REQ-CAD03", "Rejeitar valores negativos com retorno -1, conforme a regra escrita."),
    ("REQ-CAD04", "Confirmar o contrato de NULL; o retorno esperado permanece a esclarecer."),
)
SCOPE = (
    "Conformidade funcional do plano PCE/AVL da regra escrita, observada no modelo local Decimal da fonte atual. "
    "Não executa runtime Informix, SQL, transações nem homologação de cliente. "
    "NULL permanece pendente de oráculo, mesmo quando o modelo produz um valor. "
    "Esta matriz é independente da suíte de caracterização usada no escore de mutação."
)


def _requirements_for(case: dict) -> list[str]:
    if case["Ponto"] == "Nulo":
        return ["REQ-CAD04"]
    if case["Classe"] == "Inválida":
        return ["REQ-CAD03"]
    return ["REQ-CAD01", "REQ-CAD02"] if case["Ponto"] == "On-Point" else ["REQ-CAD01"]


def _verdict(tests: list[dict]) -> str:
    if any(test["status"] == "FAIL" for test in tests):
        return "Reprovado"
    if tests and all(test["status"] == "PASS" for test in tests):
        return "Aprovado"
    if not any(test["executed"] for test in tests):
        return "Sem execução"
    return "Pendente"


def validate_functional_plan(source: str, selected_ids=None) -> dict:
    """Run selected planned cases and return requirement↔test traceability.

    None selects all 15 cases; [] selects none. IDs must be unique and known.
    Model/observation limitations make a selected case pending, never PASS.
    ``executed`` counts actual model execution attempts, including observed
    NULL cases whose oracle remains pending. Unselected cases stay in the RTM.
    """
    validate_source(source)
    planned = generate_cases()
    identifiers = {case["ID"] for case in planned}
    if selected_ids is None:
        selected = identifiers
    else:
        if not isinstance(selected_ids, (list, tuple, set)) or any(not isinstance(identifier, str) for identifier in selected_ids):
            raise ValueError("Selecione uma lista de IDs de casos conhecidos.")
        if len(set(selected_ids)) != len(selected_ids):
            raise ValueError("A seleção de casos contém IDs repetidos.")
        selected = set(selected_ids)
        unknown = selected - identifiers
        if unknown:
            raise ValueError("IDs de casos desconhecidos: " + ", ".join(sorted(unknown)))
    ordered_selection = [case["ID"] for case in planned if case["ID"] in selected]
    model, model_error = None, None
    if selected:
        try:
            model = _compile_model(source)
        except (UnsupportedSyntax, ValueError, TypeError, RecursionError) as error:
            model_error = str(error)
    tests = []
    for case in planned:
        inputs = [case[parameter] for parameter in PARAMETERS]
        flow = "Principal" if case["Ponto"] == "Interior" else "Alternativo / limite" if case["Ponto"] == "On-Point" else "Exceção"
        test = {"id": case["ID"], "scenario": f"{case['Parâmetro']} — {case['Ponto']} ({case['Classe']})",
                "flow": flow, "execution_path_scope": "Classificação do cenário planejado; caminhos do programa não foram instrumentados.",
                "inputs": inputs, "requirements": _requirements_for(case),
                "expected": case["Resultado esperado"], "actual": None,
                "selected": case["ID"] in selected, "executed": False, "status": "Pendente", "reason": ""}
        if not test["selected"]:
            test["reason"] = "Não executado: caso fora da seleção desta execução."
        elif model is None:
            test["reason"] = "Não observável no modelo local: " + (model_error or "Modelo indisponível.")
        else:
            try:
                values = [_decimal(value) for value in inputs]
                test["executed"] = True
                actual = _execute_model(model, values)
                test["actual"] = _result_text(actual)
                if case["Ponto"] == "Nulo":
                    test["reason"] = "Contrato de NULL a confirmar: o valor observado não define o resultado esperado da regra escrita."
                else:
                    passed = actual == _decimal(test["expected"])
                    test["status"] = "PASS" if passed else "FAIL"
                    test["reason"] = ("Resultado observado coincide com o esperado na regra escrita (modelo local)." if passed
                                      else "Resultado observado diverge do esperado na regra escrita (modelo local).")
            except (ArithmeticError, ValueError, TypeError, RecursionError) as error:
                test["reason"] = "Execução do modelo sem resultado observável: " + str(error)
        tests.append(test)
    requirements = []
    for identifier, description in REQUIREMENTS:
        cases = [test for test in tests if identifier in test["requirements"]]
        counts = Counter(test["status"] for test in cases)
        requirements.append({"id": identifier, "description": description,
                             "planned_cases": [test["id"] for test in cases], "planned_count": len(cases),
                             "passed": counts["PASS"], "failed": counts["FAIL"], "pending": counts["Pendente"],
                             "executed": sum(test["executed"] for test in cases), "status": _verdict(cases)})
    counts = Counter(test["status"] for test in tests)
    summary = {"passed": counts["PASS"], "failed": counts["FAIL"], "pending": counts["Pendente"],
               "executed": sum(test["executed"] for test in tests), "selected": len(selected),
               "total": len(tests), "status": _verdict(tests)}
    selection_json = json.dumps(ordered_selection, separators=(",", ":"), ensure_ascii=False)
    return {"requirements": requirements, "tests": tests, "summary": summary,
            "source_sha256": sha256(source.encode("utf-8")).hexdigest(), "scope": SCOPE,
            "selected_ids": ordered_selection, "selection_sha256": sha256(selection_json.encode("utf-8")).hexdigest(),
            "model_error": model_error}
