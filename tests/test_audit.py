"""Meaningful checks for the manual oracle and conservative source inspection."""

from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from audit import (
    EPSILON,
    MAX_SOURCE_CHARS,
    boundary_rows,
    build_local_report,
    equivalence_rows,
    generate_cases,
    inspect_source,
    load_source,
    validate_source,
)


SOURCE = """FUNCTION cad0001_calcula_valor(p_val1, p_val2, p_val3)
DEFINE p_val1, p_val2, p_val3, l_val_calculado DECIMAL(12,2)
IF p_val1 IS NULL THEN LET p_val1 = 0 END IF
IF p_val2 IS NULL THEN LET p_val2 = 0 END IF
IF p_val3 IS NULL THEN LET p_val3 = 0 END IF
LET l_val_calculado = (p_val1 * p_val2) + p_val3
RETURN l_val_calculado
END FUNCTION
"""


class PlanningTests(unittest.TestCase):
    def test_partitions_cover_all_parameters_and_invalid_null(self):
        rows = equivalence_rows()
        self.assertEqual(len(rows), 9)
        for parameter in ("val_param1", "val_param2", "val_param3"):
            partitions = [row for row in rows if row["Parâmetro"] == parameter]
            self.assertEqual(len(partitions), 3)
            self.assertEqual(
                {row["Classe"] for row in partitions},
                {"Válida", "Inválida — negativos", "Inválida — nulos"},
            )

    def test_epsilon_and_required_boundary_values(self):
        self.assertEqual(EPSILON, Decimal("0.01"))
        rows = boundary_rows()
        self.assertEqual([row["Ponto"] for row in rows], ["On-Point", "Off-Point", "Interior", "Exterior"])
        self.assertEqual([str(row["Valor"]) for row in rows], ["0.0", "-0.01", "100.0", "-100.0"])

    def test_cases_isolate_one_parameter_and_separate_errors_from_ambiguous_null(self):
        rows = generate_cases()
        self.assertEqual(len(rows), 15)
        self.assertEqual(len({row["ID"] for row in rows}), 15)
        baseline = {"val_param1": "1.00", "val_param2": "1.00", "val_param3": "0.00"}
        for row in rows:
            for parameter, value in baseline.items():
                if parameter != row["Parâmetro"]:
                    self.assertEqual(row[parameter], value)
            if row["Ponto"] in ("Off-Point", "Exterior"):
                self.assertEqual(row["Resultado esperado"], "-1")
                self.assertEqual(row["Classe"], "Inválida")
            elif row["Ponto"] == "Nulo":
                self.assertEqual(row["Resultado esperado"], "A esclarecer")
                self.assertEqual(row["Classe"], "Inválida")
        self.assertEqual(sum(row["Classe"] == "Inválida" for row in rows), 9)
        self.assertEqual(sum(row["Resultado esperado"] == "-1" for row in rows), 6)

    def test_formula_results_do_not_use_float_or_rounding(self):
        rows = generate_cases()
        results = {(row["Parâmetro"], row["Ponto"]): row["Resultado esperado"] for row in rows}
        self.assertEqual(results[("val_param1", "On-Point")], "0.00")
        self.assertEqual(results[("val_param2", "Interior")], "100.00")
        self.assertEqual(results[("val_param3", "On-Point")], "1.00")
        self.assertEqual(results[("val_param3", "Interior")], "101.00")


class SourceInspectionTests(unittest.TestCase):
    def test_original_source_reveals_null_normalization_and_missing_negative_guard(self):
        evidence = inspect_source(SOURCE)
        self.assertTrue(evidence["has_null_normalization"])
        self.assertFalse(evidence["has_negative_rejection"])
        self.assertFalse(evidence["has_null_rejection"])

    def test_pdf_negative_guard_is_recognized(self):
        guarded = SOURCE.replace(
            "LET l_val_calculado =",
            "IF p_val1 < 0 OR p_val2 < 0 OR p_val3 < 0 THEN\nRETURN -1\nEND IF\nLET l_val_calculado =",
        )
        self.assertTrue(inspect_source(guarded)["has_negative_rejection"])

    def test_comments_literals_and_other_functions_are_not_evidence(self):
        decoys = (
            "# IF p_val1 < 0 OR p_val2 < 0 OR p_val3 < 0 THEN RETURN -1 END IF\n"
            '-- IF p_val1 < 0 OR p_val2 < 0 OR p_val3 < 0 THEN RETURN -1 END IF\n'
            'MESSAGE "IF p_val1 < 0 OR p_val2 < 0 OR p_val3 < 0 THEN RETURN -1 END IF"\n'
        )
        source = SOURCE.replace("RETURN l_val_calculado", decoys + "RETURN l_val_calculado")
        source += "\nFUNCTION other()\nIF p_val1 < 0 OR p_val2 < 0 OR p_val3 < 0 THEN RETURN -1 END IF\nEND FUNCTION"
        self.assertFalse(inspect_source(source)["has_negative_rejection"])

    def test_and_condition_does_not_claim_each_parameter_is_guarded(self):
        source = SOURCE.replace(
            "RETURN l_val_calculado",
            "IF p_val1 < 0 AND p_val2 < 0 AND p_val3 < 0 THEN RETURN -1 END IF\nRETURN l_val_calculado",
        )
        self.assertFalse(inspect_source(source)["has_negative_rejection"])

    def test_aliases_in_pdf_signature_are_recognized(self):
        source = """FUNCTION cad0001_calcula_valor(val_param1, val_param2, val_param3)
IF val_param1 IS NULL THEN LET p_val1 = 0 ELSE LET p_val1 = val_param1 END IF
IF val_param2 IS NULL THEN LET p_val2 = 0 ELSE LET p_val2 = val_param2 END IF
IF val_param3 IS NULL THEN LET p_val3 = 0 ELSE LET p_val3 = val_param3 END IF
IF p_val1 < 0 OR p_val2 < 0 OR p_val3 < 0 THEN RETURN -1 END IF
RETURN (p_val1 * p_val2) + p_val3
END FUNCTION
"""
        evidence = inspect_source(source)
        self.assertTrue(evidence["has_negative_rejection"])
        self.assertTrue(evidence["has_null_normalization"])

    def test_partial_guard_is_not_reported_as_complete(self):
        source = SOURCE.replace("RETURN l_val_calculado", "IF p_val1 < 0 THEN RETURN -1 END IF\nRETURN l_val_calculado")
        evidence = inspect_source(source)
        self.assertFalse(evidence["has_negative_rejection"])
        self.assertEqual(evidence["negative_rejection_parameters"], ["val_param1"])

    def test_null_rejection_is_recognized_separately(self):
        source = """FUNCTION cad0001_calcula_valor(a, b, c)
IF a IS NULL OR b IS NULL OR c IS NULL THEN RETURN -1 END IF
RETURN (a * b) + c
END FUNCTION
"""
        self.assertTrue(inspect_source(source)["has_null_rejection"])
        self.assertFalse(inspect_source(source)["has_null_normalization"])

    def test_nonzero_or_compound_assignment_is_not_null_to_zero(self):
        for replacement in ("0.01", "0 + 1"):
            source = SOURCE.replace("= 0 END IF", f"= {replacement} END IF")
            self.assertFalse(inspect_source(source)["has_null_normalization"])

    def test_invalid_input_and_comment_only_function_are_rejected(self):
        for invalid in ("", "   ", "print('hello')", "# " + SOURCE.replace("\n", "\n# "), SOURCE[:-14], "x" * (MAX_SOURCE_CHARS + 1)):
            with self.subTest(source=invalid[:40]), self.assertRaises(ValueError):
                validate_source(invalid)

    def test_source_is_data_and_is_not_executed(self):
        source = SOURCE + "\nraise RuntimeError('source must never run')"
        self.assertIn("15 casos", build_local_report(source))

    def test_report_discloses_oracle_ambiguity_and_no_4gl_execution(self):
        report = build_local_report(SOURCE)
        self.assertIn("ε = 0,01", report)
        self.assertIn("tornando a especificação inconsistente", report)
        self.assertIn("não foram executados", report)
        self.assertIn("SHA-256", report)
        self.assertIn("-0,01", report)
        self.assertIn("100,00", report)
        self.assertIn("retorno fica **a esclarecer**", report)

    def test_loading_utf8_bom_and_cp1252(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "cad0001.txt"
            text = "# Cálculo monetário\n" + SOURCE
            for encoding in ("utf-8-sig", "cp1252"):
                file.write_bytes(text.encode(encoding))
                self.assertEqual(load_source(file), text)


if __name__ == "__main__":
    unittest.main()
