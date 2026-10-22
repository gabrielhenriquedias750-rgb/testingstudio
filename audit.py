"""Deterministic PCE/AVL planning for the CAD0001 laboratory.

This module builds an oracle from the manual's written business rule. It never
executes, imports, transpiles or otherwise runs the supplied Informix-4GL source.
"""

from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import re


EPSILON = Decimal("0.01")
MAX_SOURCE_CHARS = 100_000
PARAMETERS = ("val_param1", "val_param2", "val_param3")


def _code_without_comments_or_strings(source: str) -> str:
    """Preserve newlines while hiding 4GL comments and quoted literals."""
    result: list[str] = []
    position = 0
    while position < len(source):
        char = source[position]
        if char in ("'", '"'):
            quote = char
            result.append(" ")
            position += 1
            while position < len(source):
                char = source[position]
                result.append("\n" if char == "\n" else " ")
                position += 1
                if char == quote:
                    if position < len(source) and source[position] == quote:
                        result.append(" ")
                        position += 1
                    else:
                        break
        elif char == "#" or source.startswith("--", position):
            while position < len(source) and source[position] != "\n":
                result.append(" ")
                position += 1
        else:
            result.append(char)
            position += 1
    return "".join(result)


def _function_parts(source: str) -> tuple[list[str], str]:
    code = _code_without_comments_or_strings(source)
    match = re.search(
        r"^\s*FUNCTION\s+cad0001_calcula_valor\s*\(([^)]*)\)(.*?)"
        r"^\s*END\s+FUNCTION\b",
        code,
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise ValueError(
            "A fonte deve conter a função cad0001_calcula_valor completa "
            "(FUNCTION ... END FUNCTION)."
        )
    parameters = [part.strip().lower() for part in match.group(1).split(",")]
    if len(parameters) != 3 or any(
        not re.fullmatch(r"[a-z_]\w*", parameter) for parameter in parameters
    ):
        raise ValueError("A função CAD0001 deve declarar exatamente três parâmetros.")
    return parameters, match.group(2)


def validate_source(source: str) -> None:
    """Validate an analysis input, without interpreting its instructions."""
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Informe o conteúdo do arquivo cad0001_item_calculo.txt.")
    if len(source) > MAX_SOURCE_CHARS:
        raise ValueError("A fonte excede o limite de 100.000 caracteres.")
    _function_parts(source)


def load_source(path: Path) -> str:
    """Load the required local source, accepting UTF-8/BOM and legacy CP1252."""
    raw = Path(path).read_bytes()
    try:
        source = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            source = raw.decode("cp1252")
        except UnicodeDecodeError as error:
            raise ValueError("Use uma fonte codificada em UTF-8 ou Windows-1252.") from error
    validate_source(source)
    return source


def equivalence_rows() -> list[dict[str, str]]:
    """Return the three partitions for every parameter in the manual."""
    rows = []
    for parameter in PARAMETERS:
        for classification, domain, result in (
            ("Válida", "Numérico ≥ 0,00", "Cálculo (p1 × p2) + p3"),
            ("Inválida — negativos", "Numérico < 0,00", "Erro: -1"),
            ("Inválida — nulos", "NULL / ausente", "Inválido; retorno não definido"),
        ):
            rows.append(
                {
                    "Parâmetro": parameter,
                    "Classe": classification,
                    "Domínio": domain,
                    "Resultado esperado": result,
                }
            )
    return rows


def boundary_rows() -> list[dict[str, str | float]]:
    """Return the four laboratory points; floats are only chart coordinates."""
    return [
        {
            "Ponto": "On-Point",
            "Valor": 0.0,
            "Condição": "Exatamente na fronteira válida",
            "Resultado esperado": "Sucesso (cálculo OK)",
        },
        {
            "Ponto": "Off-Point",
            "Valor": float(-EPSILON),
            "Condição": "0,00 − ε: primeiro centavo inválido",
            "Resultado esperado": "Erro: -1",
        },
        {
            "Ponto": "Interior",
            "Valor": 100.0,
            "Condição": "Região válida",
            "Resultado esperado": "Sucesso (cálculo OK)",
        },
        {
            "Ponto": "Exterior",
            "Valor": -100.0,
            "Condição": "Região inválida",
            "Resultado esperado": "Erro: -1",
        },
    ]


def generate_cases() -> list[dict[str, str]]:
    """Plan 15 isolated cases with expected values from the written rule.

    The baseline is (1.00, 1.00, 0.00). Only one input changes in each case.
    Decimal arithmetic is exact for these cases; no rounding policy is inferred
    for the legacy runtime.
    """
    points = (
        ("On-Point", Decimal("0.00")),
        ("Off-Point", -EPSILON),
        ("Interior", Decimal("100.00")),
        ("Exterior", Decimal("-100.00")),
        ("Nulo", None),
    )
    rows = []
    for index, parameter in enumerate(PARAMETERS):
        for point_name, point in points:
            values = [Decimal("1.00"), Decimal("1.00"), Decimal("0.00")]
            values[index] = point
            invalid = point is None or point < 0
            if invalid:
                result = "A esclarecer" if point is None else "-1"
                reason = (
                    "NULL é inválido na classificação textual, mas o exemplo o "
                    "converte para zero; o retorno esperado precisa ser esclarecido."
                    if point is None
                    else "Valor negativo é inválido pela regra textual do manual."
                )
            else:
                result = format(values[0] * values[1] + values[2], ".2f")
                reason = "Entradas não negativas: aplicar (p1 × p2) + p3."
            row = {
                "ID": f"CT-{len(rows) + 1:02d}",
                "Parâmetro": parameter,
                "Ponto": point_name,
                **{
                    name: "NULL" if value is None else format(value, ".2f")
                    for name, value in zip(PARAMETERS, values)
                },
                "Classe": "Inválida" if invalid else "Válida",
                "Resultado esperado": result,
                "Motivo": reason,
            }
            rows.append(row)
    return rows


def inspect_source(source: str) -> dict[str, object]:
    """Identify explicit guards in the target function conservatively.

    Supported evidence: direct NULL-to-zero assignments and OR-joined negative
    or NULL checks returning -1. Absence of a recognized pattern does not prove
    absence of other equivalent logic. Strings/comments and other functions
    are excluded from the inspection.
    """
    validate_source(source)
    source_parameters, body = _function_parts(source)
    aliases = {parameter: index for index, parameter in enumerate(source_parameters)}
    for alias, original in re.findall(
        r"\bLET\s+([a-z_]\w*)\s*=\s*([a-z_]\w*)\b", body, re.IGNORECASE
    ):
        if original.lower() in source_parameters and alias.lower() not in source_parameters:
            aliases[alias.lower()] = aliases[original.lower()]

    null_normalization: set[int] = set()
    negative_rejection: set[int] = set()
    null_rejection: set[int] = set()
    blocks = re.finditer(
        r"\bIF\b(.*?)\bTHEN\b(.*?)\bEND\s+IF\b",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for block in blocks:
        condition, consequence = block.group(1).strip(), block.group(2).strip()
        null_condition = re.fullmatch(r"([a-z_]\w*)\s+IS\s+NULL", condition, re.I)
        if null_condition:
            input_name = null_condition.group(1).lower()
            zero_assignment = re.fullmatch(
                r"LET\s+([a-z_]\w*)\s*=\s*0(?:\.0+)?"
                r"(?:\s+ELSE\s+LET\s+\1\s*=\s*([a-z_]\w*))?\s*",
                consequence,
                re.I,
            )
            if (
                input_name in aliases
                and zero_assignment
                and aliases.get(zero_assignment.group(1).lower()) == aliases[input_name]
                and (
                    zero_assignment.group(2) is None
                    or aliases.get(zero_assignment.group(2).lower()) == aliases[input_name]
                )
            ):
                null_normalization.add(aliases[input_name])

        # Only an immediate -1 return is evidence; nested or compound bodies
        # deliberately remain unrecognized rather than being overinterpreted.
        if not re.fullmatch(r"RETURN\s+-1(?:\.0+)?\s*", consequence, re.I):
            continue
        terms = re.split(r"\s+OR\s+", condition, flags=re.I)
        negatives: set[int] = set()
        nulls: set[int] = set()
        all_negative = all_null = True
        for term in terms:
            term = term.strip()
            negative_match = re.fullmatch(
                r"([a-z_]\w*)\s*<\s*0(?:\.0+)?", term, re.I
            )
            null_match = re.fullmatch(r"([a-z_]\w*)\s+IS\s+NULL", term, re.I)
            if negative_match and negative_match.group(1).lower() in aliases:
                negatives.add(aliases[negative_match.group(1).lower()])
            else:
                all_negative = False
            if null_match and null_match.group(1).lower() in aliases:
                nulls.add(aliases[null_match.group(1).lower()])
            else:
                all_null = False
        if all_negative:
            negative_rejection.update(negatives)
        if all_null:
            null_rejection.update(nulls)

    return {
        "function_name": "cad0001_calcula_valor",
        "parameters": source_parameters,
        "null_normalization_parameters": [PARAMETERS[i] for i in sorted(null_normalization)],
        "negative_rejection_parameters": [PARAMETERS[i] for i in sorted(negative_rejection)],
        "null_rejection_parameters": [PARAMETERS[i] for i in sorted(null_rejection)],
        "has_negative_rejection": len(negative_rejection) == 3,
        "has_null_normalization": len(null_normalization) == 3,
        "has_null_rejection": len(null_rejection) == 3,
        "sha256": sha256(source.encode("utf-8")).hexdigest(),
    }


def _markdown_table(rows: list[dict[str, object]]) -> str:
    columns = list(rows[0])
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    def format_cell(column: str, value: object) -> str:
        if column == "Valor" and isinstance(value, (float, Decimal)):
            return format(value, ".2f").replace(".", ",")
        return str(value)
    lines.extend("| " + " | ".join(format_cell(column, row[column]) for column in columns) + " |" for row in rows)
    return "\n".join(lines)


def build_local_report(source: str) -> str:
    """Build a reproducible, offline analysis and test plan in Portuguese."""
    evidence = inspect_source(source)
    if evidence["has_negative_rejection"]:
        negative_finding = (
            "Foi identificado um padrão explícito de rejeição de negativos com "
            "RETURN -1 para os três parâmetros."
        )
    else:
        negative_finding = (
            "Não foi identificado um padrão explícito de rejeição de negativos com "
            "RETURN -1 para os três parâmetros. Revise esse ponto frente à regra "
            "do manual, que exige rejeição de qualquer valor negativo."
        )
    if evidence["has_null_normalization"]:
        null_finding = (
            "Foram identificadas atribuições de zero quando os três parâmetros "
            "são NULL. Esse tratamento conflita com a regra textual do manual, "
            "que classifica NULL como inválido. O exemplo de código do próprio PDF "
                "também converte NULL para zero, tornando a especificação inconsistente. "
                "O retorno esperado para NULL está a esclarecer: o manual não define "
                "inequivocamente um código de erro para essa classe."
        )
    elif evidence["has_null_rejection"]:
        null_finding = "Foi identificado um padrão explícito de rejeição de NULL com RETURN -1."
    else:
        null_finding = (
            "Não foi reconhecido um tratamento explícito de NULL para os três "
            "parâmetros; confirme esse comportamento no ambiente Informix-4GL."
        )
    return "\n\n".join(
        [
            "# Auditoria local — CAD0001 / Sprint 1",
            (
                "**Método:** plano determinístico de caixa-preta baseado na regra "
                "textual do manual, acompanhado de inspeção estática da fonte. "
                "Os resultados são esperados; o programa 4GL e suas operações SQL "
                "não foram executados."
            ),
            "## Particionamento em Classes de Equivalência (PCE)",
            _markdown_table(equivalence_rows()),
            "## Análise do Valor Limite (AVL)",
            (
                "A fronteira inferior válida é **0,00**. Como o domínio monetário "
                "usa duas casas decimais (DECIMAL(12,2)), a menor variação "
                "representável é **ε = 0,01 (um centavo)**. Portanto, o ponto "
                "imediatamente exterior é **0,00 − ε = −0,01**."
            ),
            _markdown_table(boundary_rows()),
            "## Evidências e divergências da fonte",
            negative_finding,
            null_finding,
            (
                "A detecção reconhece somente padrões explícitos dentro de "
                "cad0001_calcula_valor, ignorando comentários, textos e outras "
                "funções. Um padrão não reconhecido exige revisão; sua ausência "
                "não prova ausência de lógica equivalente."
            ),
            "## Plano de testes reproduzível",
            (
                "São **15 casos**: cinco por parâmetro (On, Off, Interior, Exterior "
                "e NULL). A base é **(1,00; 1,00; 0,00)** e apenas um parâmetro "
                "varia por caso. O oráculo rejeita negativos com **-1**; NULL é "
                "classificado como inválido, mas seu retorno fica **a esclarecer** "
                "diante da inconsistência da especificação. Entradas válidas usam "
                "**(p1 × p2) + p3** com Decimal. A tabela "
                "de casos pode ser baixada na interface."
            ),
            (
                "Para obter um veredito de execução, execute os casos no ambiente "
                "legado e compare os retornos efetivos. Estes casos evitam "
                "overflow e arredondamento intermediário; esses comportamentos "
                "dependem de validação adicional no runtime original."
            ),
            f"**SHA-256 da fonte analisada:** `{evidence['sha256']}`",
        ]
    )
