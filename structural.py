"""Source-dependent structural analysis for the documented CAD0001 4GL subset.

Public, JSON-serializable APIs:
* analyze_source(source): functions, CFG nodes/edges, basis paths and Def-Use.
* cfg_dot(function): Graphviz text suitable for st.graphviz_chart.
* default_mutation_cases(): editable cases using the supplied source's contract.
* run_mutation_analysis(source, cases, manual_equivalents=()): execute a bounded
  local arithmetic model of original and actual source mutants, never 4GL.

The parser accepts acyclic FUNCTION bodies, DEFINE, IF/THEN/ELSE/END IF,
LET, RETURN, INITIALIZE, CALL, MESSAGE, SQL DML, WHENEVER and transaction
statements. Unknown control syntax is rejected for that function. SQL, CALL
and implicit runtime errors have no internal control edges in this model.
"""

from __future__ import annotations

from collections import deque
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import json
import re


MAX_SOURCE_CHARS = 100_000
MAX_CASES = 200
MAX_CFG_NODES = 500
MAX_DU_PAIRS = 5_000
MAX_MUTANTS = 100
_IDENT = r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*|\.\*)?"
_KEYWORDS = set("AND OR NOT IS NULL TRUE FALSE DECIMAL INTEGER SMALLINT CHAR VARCHAR LIKE TO THEN RETURN LET INITIALIZE CALL MESSAGE DEFINE RECORD END SQLCA".lower().split())
_START = re.compile(r"(?im)^[ \t]*(DEFINE|LET|RETURN|INITIALIZE|CALL|MESSAGE|INSERT|UPDATE|DELETE|SELECT|WHENEVER|BEGIN|COMMIT|ROLLBACK|WHILE|FOR|FOREACH|CASE|GOTO|EXIT|CONTINUE|SLEEP|DISPLAY|INPUT|MENU|END)\b")
LIMITATIONS = [
    "Subconjunto acíclico de Informix-4GL; laços, CASE, GOTO e sintaxe desconhecida são recusados por função.",
    "SQL e CALL são opacos; não se inferem decisões internas, exceções implícitas nem efeitos internos das chamadas.",
    "DML e BEGIN/COMMIT/ROLLBACK definem virtualmente sqlca.sqlcode; campos globais lidos são entradas externas da função.",
    "Caminhos são estruturais; viabilidade semântica de predicados não é provada. A base é independente sobre GF(2).",
    "Def-Uso é intraprocedural; declarações locais não contam como atribuições. INITIALIZE ... TO NULL conta como definição explícita.",
]


class UnsupportedSyntax(ValueError):
    """The source is outside the explicitly supported analysis subset."""


def _mask(source: str, *, strings: bool = False) -> str:
    """Remove comments, optionally strings, preserving offsets and line numbers."""
    chars = list(source)
    i = 0
    while i < len(source):
        if source[i] in "\"'":
            quote = source[i]
            start = i
            i += 1
            while i < len(source):
                if source[i] == quote:
                    i += 1
                    if i < len(source) and source[i] == quote:
                        i += 1
                        continue
                    break
                i += 1
            else:
                raise UnsupportedSyntax("Literal de texto sem fechamento.")
            if strings:
                for j in range(start, i):
                    if chars[j] != "\n":
                        chars[j] = " "
        elif source[i] == "#" or source.startswith("--", i):
            while i < len(source) and source[i] != "\n":
                chars[i] = " "
                i += 1
        else:
            i += 1
    return "".join(chars)


def _line(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _statement_items(source: str, start: int, end: int) -> list[dict]:
    clean = _mask(source)
    hidden = _mask(source, strings=True)
    items: list[dict] = []
    controls = list(re.finditer(r"\bEND\s+IF\b|\bIF\b|\bTHEN\b|\bELSE\b", hidden[start:end], re.I))
    position = start

    def statements(a: int, b: int) -> None:
        segment = clean[a:b]
        matches = list(_START.finditer(segment))
        # Inline statements immediately following THEN/ELSE have no line prefix.
        first_nonblank = len(segment) - len(segment.lstrip())
        if segment.strip() and (not matches or matches[0].start() > first_nonblank):
            beginning = re.match(r"\s*([A-Za-z_]\w*)\b", segment)
            if not beginning or beginning.group(1).upper() not in {
                "DEFINE", "LET", "RETURN", "INITIALIZE", "CALL", "MESSAGE",
                "INSERT", "UPDATE", "DELETE", "SELECT", "WHENEVER", "BEGIN", "COMMIT", "ROLLBACK",
            }:
                raise UnsupportedSyntax(f"Linha {_line(source, a)}: instrução desconhecida: {segment.strip()[:70]}")
            matches = [re.match(r"\s*([A-Za-z_]\w*)\b", segment)] + matches
        for index, match in enumerate(matches):
            local_end = matches[index + 1].start() if index + 1 < len(matches) else len(segment)
            raw = segment[match.start():local_end]
            leading = len(raw) - len(raw.lstrip())
            trailing = len(raw.rstrip())
            if not raw.strip():
                continue
            begin = a + match.start() + leading
            finish = a + match.start() + trailing
            items.append({"kind": match.group(1).lower(), "text": clean[begin:finish], "start": begin, "end": finish, "line": _line(source, begin)})

    pending_if = None
    for match in controls:
        begin, finish = start + match.start(), start + match.end()
        keyword = re.sub(r"\s+", " ", match.group().upper())
        if pending_if is not None:
            if keyword != "THEN":
                raise UnsupportedSyntax(f"Linha {_line(source, pending_if)}: IF sem THEN ou condição não suportada.")
            condition = clean[pending_if + 2:begin].strip()
            if not condition:
                raise UnsupportedSyntax("IF sem condição.")
            items.append({"kind": "if", "text": condition, "start": pending_if, "end": finish, "line": _line(source, pending_if)})
            pending_if = None
        else:
            statements(position, begin)
            if keyword == "IF":
                pending_if = begin
            elif keyword == "THEN":
                raise UnsupportedSyntax(f"Linha {_line(source, begin)}: THEN sem IF.")
            else:
                items.append({"kind": keyword.lower().replace(" ", "_"), "text": keyword, "start": begin, "end": finish, "line": _line(source, begin)})
        position = finish
    if pending_if is not None:
        raise UnsupportedSyntax("IF sem THEN.")
    statements(position, end)
    return items


def _declarations(text: str) -> set[str]:
    body = re.sub(r"^DEFINE\s+", "", text.strip(), flags=re.I)
    if re.search(r"\bRECORD\b", body, re.I):
        raise UnsupportedSyntax("DEFINE RECORD local não suportado; use o RECORD global documentado.")
    # Split commas outside type arguments, e.g. DECIMAL(12,2).
    parts = re.split(r",(?![^()]*\))", body)
    names = set()
    for part in parts:
        found = re.fullmatch(r"\s*([A-Za-z_]\w*)(?:\s+(?:DECIMAL\s*\(\s*\d+\s*,\s*\d+\s*\)|(?:CHAR|VARCHAR)\s*\(\s*\d+\s*\)|INTEGER|SMALLINT|FLOAT|DATE|BOOLEAN|LIKE\s+[\w.]+))?\s*", part, re.I)
        if not found:
            raise UnsupportedSyntax(f"Declaração não suportada: {part.strip()[:70]}")
        names.add(found.group(1).lower())
    return names


def _parse_function(source: str, match: re.Match, finish: re.Match) -> dict:
    params_text = match.group(2).strip()
    params = [name.strip().lower() for name in params_text.split(",")] if params_text else []
    if any(not re.fullmatch(r"[a-z_]\w*", name) for name in params) or len(set(params)) != len(params):
        raise UnsupportedSyntax("Lista de parâmetros não suportada.")
    items = _statement_items(source, match.end(), finish.start())
    declared = set(params)
    index = 0

    def block(nested: bool = False, depth: int = 0) -> list[dict]:
        nonlocal index
        if depth > 40:
            raise UnsupportedSyntax("Aninhamento de IF excede o limite de 40 níveis.")
        result = []
        while index < len(items):
            item = items[index]
            if item["kind"] in {"else", "end_if"}:
                if not nested:
                    raise UnsupportedSyntax(f"Linha {item['line']}: {item['text']} sem IF.")
                break
            index += 1
            if item["kind"] == "define":
                declared.update(_declarations(item["text"]))
                continue
            if item["kind"] == "if":
                item["yes"] = block(True, depth + 1)
                item["no"] = []
                if index < len(items) and items[index]["kind"] == "else":
                    index += 1
                    item["no"] = block(True, depth + 1)
                if index >= len(items) or items[index]["kind"] != "end_if":
                    raise UnsupportedSyntax(f"Linha {item['line']}: IF sem END IF.")
                item["end"] = items[index]["end"]
                index += 1
            elif item["kind"] not in {"let", "return", "initialize", "call", "message", "insert", "update", "delete", "select", "whenever", "begin", "commit", "rollback"}:
                raise UnsupportedSyntax(f"Linha {item['line']}: {item['kind'].upper()} fora do subconjunto suportado.")
            _validate_statement(item)
            result.append(item)
        return result

    ast = block()
    return {"name": match.group(1).lower(), "parameters": params, "declared": declared, "ast": ast, "start": match.start(), "end": finish.end()}


def _validate_statement(item: dict) -> None:
    text, kind = item["text"], item["kind"]
    if kind == "let" and not re.fullmatch(rf"LET\s+({_IDENT})\s*=\s*\S[\s\S]*", text, re.I):
        raise UnsupportedSyntax(f"Linha {item['line']}: LET não suportado.")
    if kind in {"let", "if", "return"}:
        expression = text
        if kind == "let":
            expression = text.split("=", 1)[1]
        elif kind == "return":
            expression = re.sub(r"^RETURN\b\s*", "", text, flags=re.I)
        if expression.strip():
            _Expression(expression, set(), structural=True)
        elif kind != "return":
            raise UnsupportedSyntax(f"Linha {item['line']}: expressão vazia.")
    if kind == "initialize" and not re.fullmatch(rf"INITIALIZE\s+({_IDENT}(?:\s*,\s*{_IDENT})*)\s+TO\s+NULL", text, re.I):
        raise UnsupportedSyntax(f"Linha {item['line']}: somente INITIALIZE ... TO NULL é suportado.")
    if kind == "whenever" and not re.fullmatch(r"WHENEVER\s+ERROR\s+(?:CONTINUE|STOP)", text, re.I):
        raise UnsupportedSyntax(f"Linha {item['line']}: WHENEVER com desvio não é suportado.")
    if kind in {"begin", "commit", "rollback"} and not re.fullmatch(r"(?:BEGIN|COMMIT|ROLLBACK)\s+WORK", text, re.I):
        raise UnsupportedSyntax(f"Linha {item['line']}: transação não suportada.")
    if kind == "call":
        expression = re.sub(r"^CALL\s+", "", text, flags=re.I)
        parts = re.split(r"\bRETURNING\b", expression, flags=re.I)
        if len(parts) > 2 or (len(parts) == 2 and not re.fullmatch(rf"\s*{_IDENT}(?:\s*,\s*{_IDENT})*\s*", parts[1])):
            raise UnsupportedSyntax(f"Linha {item['line']}: CALL RETURNING não suportado.")
        _Expression(parts[0], set(), structural=True)
    if kind == "message":
        expression = re.sub(r"^MESSAGE\s+", "", text, flags=re.I)
        masked = _mask(expression, strings=True)
        depth, start = 0, 0
        for offset, char in enumerate(masked + ","):
            depth += (char == "(") - (char == ")")
            if char == "," and depth == 0:
                _Expression(expression[start:offset], set(), structural=True)
                start = offset + 1
    # Reject swallowed statements/constructs instead of pretending they are a node.
    if kind not in {"insert", "update", "delete", "select", "message"}:
        if re.search(r"(?im)^\s*(?:WHILE|FOR|FOREACH|CASE|GOTO|SLEEP|DISPLAY|INPUT|MENU)\b", text):
            raise UnsupportedSyntax(f"Linha {item['line']}: construção desconhecida.")


def _source_functions(source: str) -> list[dict]:
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Informe a fonte 4GL original.")
    if len(source) > MAX_SOURCE_CHARS:
        raise ValueError("Fonte maior que 100.000 caracteres.")
    hidden = _mask(source, strings=True)
    starts = list(re.finditer(r"(?im)^[ \t]*FUNCTION\s+([A-Za-z_]\w*)\s*\(([^)]*)\)", hidden))
    ends = list(re.finditer(r"(?im)^[ \t]*END\s+FUNCTION\b", hidden))
    if not starts:
        raise ValueError("Nenhuma FUNCTION completa encontrada na fonte.")
    if len(starts) > 200:
        raise ValueError("Análise limitada a 200 funções por fonte.")
    result = []
    seen = set()
    for index, match in enumerate(starts):
        name = match.group(1).lower()
        next_start = starts[index + 1].start() if index + 1 < len(starts) else len(source)
        finish = next((end for end in ends if match.end() <= end.start() < next_start), None)
        try:
            if name in seen:
                raise UnsupportedSyntax("Nome de função duplicado.")
            if finish is None:
                raise UnsupportedSyntax("FUNCTION sem END FUNCTION.")
            result.append(_parse_function(source, match, finish))
        except (UnsupportedSyntax, RecursionError) as error:
            result.append({"name": name, "error": str(error), "parameters": []})
        seen.add(name)
    return result


def _record_fields(source: str) -> dict[str, list[str]]:
    clean = _mask(source, strings=True)
    fields = {}
    for match in re.finditer(r"\bDEFINE\s+([A-Za-z_]\w*)\s+RECORD\b(.*?)\bEND\s+RECORD\b", clean, re.I | re.S):
        record = match.group(1).lower()
        fields[record] = [f"{record}.{field.lower()}" for field in re.findall(r"(?m)^\s*([A-Za-z_]\w*)\s+(?:CHAR|VARCHAR|INTEGER|DECIMAL|SMALLINT|FLOAT|DATE)\b", match.group(2), re.I)]
    return fields


def _variables(text: str, known: set[str], *, sql: bool = False) -> list[str]:
    clean = _mask(text, strings=True)
    variables = set()
    for match in re.finditer(_IDENT, clean):
        name = match.group().lower()
        if name in _KEYWORDS or re.match(r"\s*\(", clean[match.end():]):
            continue
        if not sql or name in known or "." in name:
            variables.add(name)
    return sorted(variables)


def _effects(item: dict, declared: set[str], records: dict) -> tuple[list[str], list[str]]:
    text, kind = item["text"], item["kind"]
    known = declared | {name for fields in records.values() for name in fields} | {"sqlca.sqlcode"}
    if kind == "let":
        target, expression = re.split(r"=", re.sub(r"^LET\s+", "", text, flags=re.I), maxsplit=1)
        return [target.strip().lower()], _variables(expression, known)
    if kind == "initialize":
        targets = re.sub(r"^INITIALIZE\s+|\s+TO\s+NULL$", "", text.strip(), flags=re.I)
        definitions = []
        for target in targets.split(","):
            name = target.strip().lower()
            definitions.extend(records.get(name[:-2], [name]) if name.endswith(".*") else [name])
        return sorted(set(definitions)), []
    if kind in {"insert", "update", "delete", "select"}:
        definitions = ["sqlca.sqlcode"]
        uses = _variables(text, known, sql=True)
        # SELECT ... INTO destinations are assignments; the SELECT remains opaque.
        into = re.search(r"\bINTO\s+(.+?)(?:\bFROM\b|$)", _mask(text, strings=True), re.I | re.S) if kind == "select" else None
        if into:
            targets = _variables(into.group(1), known, sql=True)
            definitions += targets
            # Only the INTO occurrence is a write: a destination can also be
            # read in WHERE or the select-list before its new value is assigned.
            read_text = text[:into.start(1)] + " " * len(into.group(1)) + text[into.end(1):]
            uses = _variables(read_text, known, sql=True)
        return sorted(set(definitions)), uses
    if kind in {"begin", "commit", "rollback"}:
        return ["sqlca.sqlcode"], []
    if kind == "if":
        return [], _variables(text, known)
    if kind in {"return", "message"}:
        return [], _variables(re.sub(r"^\w+\s*", "", text), known)
    if kind == "call":
        arguments = re.sub(r"^CALL\s+[\w.]+", "", text, flags=re.I)
        if re.search(r"\bRETURNING\b", arguments, re.I):
            expression, targets = re.split(r"\bRETURNING\b", arguments, flags=re.I)
            return _variables(targets, known), _variables(expression, known)
        return [], _variables(arguments, known)
    return [], []


def _cfg(function: dict, records: dict) -> dict:
    nodes = [
        {"id": "n0", "kind": "entry", "label": "ENTRADA", "line": None, "defs": [], "uses": []},
        {"id": "n1", "kind": "exit", "label": "SAÍDA", "line": None, "defs": [], "uses": []},
    ]
    edges: list[dict] = []
    warnings: list[str] = []

    def connect(frontier: list[tuple[str, str]], target: str) -> None:
        for origin, label in frontier:
            edges.append({"id": f"e{len(edges)}", "source": origin, "target": target, "label": label})

    def block(statements: list[dict], frontier: list[tuple[str, str]]) -> list[tuple[str, str]]:
        for item in statements:
            if not frontier:
                warnings.append(f"Linha {item['line']}: instrução inalcançável após RETURN; excluída do GFC executável.")
                continue
            identifier = f"n{len(nodes)}"
            if len(nodes) >= MAX_CFG_NODES:
                raise UnsupportedSyntax(f"GFC excede o limite de {MAX_CFG_NODES} nós por função.")
            definitions, uses = _effects(item, function["declared"], records)
            label = ("IF " if item["kind"] == "if" else "") + " ".join(item["text"].split())
            nodes.append({"id": identifier, "kind": item["kind"], "label": label, "line": item["line"], "defs": definitions, "uses": uses})
            connect(frontier, identifier)
            if item["kind"] == "if":
                frontier = block(item["yes"], [(identifier, "V")]) + block(item["no"], [(identifier, "F")])
            elif item["kind"] == "return":
                connect([(identifier, "RETURN")], "n1")
                frontier = []
            else:
                frontier = [(identifier, "")]
        return frontier

    connect(block(function["ast"], [("n0", "")]), "n1")
    all_names = {name for node in nodes for name in node["defs"] + node["uses"]}
    if len(all_names) > 1_000:
        raise UnsupportedSyntax("Análise limitada a 1.000 variáveis por função.")
    external = sorted(all_names - function["declared"])
    nodes[0]["defs"] = sorted(set(function["parameters"]) | set(external))
    paths, rank = _basis_paths(nodes, edges)
    complexity = len(edges) - len(nodes) + 2
    result = {
        "name": function["name"], "supported": True, "errors": [],
        "parameters": function["parameters"], "external_inputs": external,
        "limitations": LIMITATIONS + warnings, "nodes": nodes, "edges": edges,
        "metrics": {"nodes": len(nodes), "edges": len(edges), "decisions": sum(node["kind"] == "if" for node in nodes), "cyclomatic": complexity, "formula": f"{len(edges)} - {len(nodes)} + 2 = {complexity}", "basis_rank": rank, "basis_complete": rank == complexity},
        "basis_paths": paths,
        "effort": {"minimum_basis_tests": complexity, "statement_nodes": len(nodes) - 2, "note": "Estimativa estrutural de casos independentes; não é prazo nem garantia de cobertura sem executar casos viáveis."},
    }
    result.update(_def_use(nodes, edges, function["declared"] - set(function["parameters"])))
    return result


def _shortest_edges(edges: list[dict], start: str, target: str, forbidden: set[str] | None = None) -> list[dict] | None:
    adjacency: dict[str, list[dict]] = {}
    for edge in edges:
        adjacency.setdefault(edge["source"], []).append(edge)
    queue = deque([start])
    seen = {start}
    previous: dict[str, dict] = {}
    while queue:
        node = queue.popleft()
        if node == target:
            path = []
            while node != start:
                edge = previous[node]
                path.append(edge)
                node = edge["source"]
            return list(reversed(path))
        if forbidden and node in forbidden and node != start:
            continue
        for edge in adjacency.get(node, []):
            if edge["target"] not in seen:
                seen.add(edge["target"])
                previous[edge["target"]] = edge
                queue.append(edge["target"])
    return None


def _basis_paths(nodes: list[dict], edges: list[dict]) -> tuple[list[dict], int]:
    candidates = []
    baseline = _shortest_edges(edges, "n0", "n1")
    if baseline is not None:
        candidates.append(baseline)
    for edge in edges:
        prefix = _shortest_edges(edges, "n0", edge["source"])
        suffix = _shortest_edges(edges, edge["target"], "n1")
        if prefix is not None and suffix is not None:
            candidates.append(prefix + [edge] + suffix)
    pivots: dict[int, int] = {}
    basis = []
    indexes = {edge["id"]: index for index, edge in enumerate(edges)}
    for path in candidates:
        vector = 0
        for edge in path:
            vector ^= 1 << indexes[edge["id"]]
        reduced = vector
        while reduced:
            pivot = reduced.bit_length() - 1
            if pivot in pivots:
                reduced ^= pivots[pivot]
            else:
                pivots[pivot] = reduced
                basis.append({"id": f"P{len(basis) + 1}", "nodes": ["n0"] + [edge["target"] for edge in path], "edges": [edge["id"] for edge in path], "branches": [{"node": edge["source"], "outcome": edge["label"]} for edge in path if edge["label"] in {"V", "F"}], "feasibility": "Não provada; requer dados de teste que satisfaçam os predicados."})
                break
    return basis, len(pivots)


def _def_use(nodes: list[dict], edges: list[dict], locals_without_entry_def: set[str]) -> dict:
    by_id = {node["id"]: node for node in nodes}
    definitions = {(node["id"], variable) for node in nodes for variable in node["defs"]}
    uninitialized = {("UNDEFINED", variable) for variable in locals_without_entry_def}
    incoming = {node["id"]: set() for node in nodes}
    outgoing = {node["id"]: set() for node in nodes}
    changed = True
    while changed:
        changed = False
        for node in nodes:
            ident = node["id"]
            reaching = set().union(*(outgoing[edge["source"]] for edge in edges if edge["target"] == ident))
            if ident == "n0":
                reaching |= uninitialized
            generated = {(ident, variable) for variable in node["defs"]}
            new_out = {definition for definition in reaching if definition[1] not in node["defs"]} | generated
            if reaching != incoming[ident] or new_out != outgoing[ident]:
                incoming[ident], outgoing[ident] = reaching, new_out
                changed = True
    pairs = []
    anomalies = []
    truncated = False
    for node in nodes:
        for variable in node["uses"]:
            reaching = sorted(definition for definition in incoming[node["id"]] if definition[1] == variable)
            for origin, _ in reaching:
                if len(pairs) >= MAX_DU_PAIRS:
                    truncated = True
                    break
                if origin == "UNDEFINED":
                    forbidden = {candidate["id"] for candidate in nodes if variable in candidate["defs"]}
                    witness = _shortest_edges(edges, "n0", node["id"], forbidden)
                    anomalies.append({"kind": "use-without-definition", "variable": variable, "node": node["id"], "line": node["line"], "description": "Há caminho que chega ao uso sem definição local explícita.", "evidence_path": ["n0"] + [edge["target"] for edge in witness or []]})
                    continue
                forbidden = {candidate["id"] for candidate in nodes if variable in candidate["defs"] and candidate["id"] not in {origin, node["id"]}}
                witness = _shortest_edges(edges, origin, node["id"], forbidden)
                base = {"variable": variable, "definition": origin, "definition_line": by_id[origin]["line"], "use": node["id"], "use_line": node["line"], "use_type": "p-use" if node["kind"] == "if" else "c-use", "path": [origin] + [edge["target"] for edge in witness or []]}
                if node["kind"] == "if":
                    for edge in edges:
                        if edge["source"] == node["id"]:
                            pairs.append({**base, "edge": edge["id"], "branch": edge["label"], "path": base["path"] + [edge["target"]]})
                else:
                    pairs.append({**base, "edge": None, "branch": None})
    consumed = {(pair["definition"], pair["variable"]) for pair in pairs}
    for origin, variable in sorted(definitions - consumed) if not truncated else []:
        if origin != "n0":
            anomalies.append({"kind": "definition-without-use", "variable": variable, "node": origin, "line": by_id[origin]["line"], "description": "Esta definição não alcança uso no modelo intraprocedural; efeito externo pode ser intencional.", "evidence_path": [origin]})
    adjacency: dict[str, list[dict]] = {}
    for edge in edges:
        adjacency.setdefault(edge["source"], []).append(edge)
    for origin, variable in sorted(definitions):
        if origin == "n0":
            continue
        queue = deque([(edge["target"], [origin, edge["target"]]) for edge in adjacency.get(origin, [])])
        seen = {origin}
        while queue:
            target, path = queue.popleft()
            if target in seen:
                continue
            seen.add(target)
            node = by_id[target]
            if variable in node["uses"]:
                continue
            if variable in node["defs"]:
                anomalies.append({"kind": "definition-redefined-without-use", "variable": variable, "node": target, "line": node["line"], "description": f"Definição de {origin} sobrescrita antes de uso neste caminho.", "evidence_path": path})
                continue
            queue.extend((edge["target"], path + [edge["target"]]) for edge in adjacency.get(target, []))
    serial = lambda values: [{"definition": origin, "variable": variable} for origin, variable in sorted(values)]
    if truncated:
        anomalies.append({"kind": "analysis-limit", "variable": "", "node": "", "line": None, "description": f"Tabela Def-Uso truncada em {MAX_DU_PAIRS} pares; cobertura completa não pode ser afirmada.", "evidence_path": []})
    return {"def_use": pairs, "def_use_complete": not truncated, "anomalies": anomalies, "reaching_definitions": [{"node": node["id"], "in": serial(incoming[node["id"]]), "out": serial(outgoing[node["id"]])} for node in nodes]}


def analyze_source(source: str) -> dict:
    """Analyze every function independently; unsupported bodies have no fake CFG."""
    functions = _source_functions(source)
    records = _record_fields(source)
    results = []
    for function in functions:
        if "error" in function:
            results.append({"name": function["name"], "supported": False, "errors": [function["error"]], "limitations": LIMITATIONS, "nodes": [], "edges": [], "basis_paths": [], "def_use": [], "anomalies": [], "metrics": None})
        else:
            try:
                results.append(_cfg(function, records))
            except UnsupportedSyntax as error:
                results.append({"name": function["name"], "supported": False, "errors": [str(error)], "limitations": LIMITATIONS, "nodes": [], "edges": [], "basis_paths": [], "def_use": [], "anomalies": [], "metrics": None})
    return {"source_sha256": sha256(source.encode("utf-8")).hexdigest(), "functions": results, "limitations": LIMITATIONS}


def cfg_dot(function: dict) -> str:
    """Return an escaped Graphviz CFG; unsupported functions are rejected."""
    if not function.get("supported"):
        raise ValueError("Função não suportada: não há GFC confiável para exibir.")
    lines = ["digraph CFG {", 'rankdir=TB; node [fontname="Arial", fontsize=10];']
    for node in function["nodes"]:
        shape = "diamond" if node["kind"] == "if" else "oval" if node["kind"] in {"entry", "exit"} else "box"
        label = f"{node['id']} · L{node['line']}\n{node['label']}" if node["line"] else f"{node['id']} · {node['label']}"
        lines.append(f"{node['id']} [shape={shape},label={json.dumps(label, ensure_ascii=False)}];")
    for edge in function["edges"]:
        lines.append(f"{edge['source']} -> {edge['target']} [label={json.dumps(edge['label'])}];")
    return "\n".join(lines + ["}"])


def default_mutation_cases() -> list[dict]:
    """Oracle for the supplied code's model (not the conflicting written rule)."""
    data = [
        ("M01", ["2", "3", "4"], "10"),
        ("M02", ["0", "3", "4"], "4"),
        ("M03", [None, "3", "4"], "4"),
        ("M04", ["2", None, "4"], "4"),
        ("M05", ["2", "3", None], "6"),
        ("M06", [None, None, None], "0"),
        ("M07", ["1.25", "2", "0.50"], "3.00"),
        ("M08", ["-2", "3", "4"], "-2"),
    ]
    return [{"id": name, "inputs": inputs, "expected": expected} for name, inputs, expected in data]


class _Expression:
    """Tiny non-Python expression parser; no eval, exec, imports or calls."""

    def __init__(self, text: str, names: set[str], *, structural: bool = False):
        token = re.compile(r'''\s*(<>|<=|>=|[(),+*/=<>-]|(?:\d+(?:\.\d*)?|\.\d+)|[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?|"(?:[^"]|"")*"|'(?:[^']|'')*')''')
        self.tokens = []
        offset = 0
        while offset < len(text):
            if not text[offset:].strip():
                break
            match = token.match(text, offset)
            if not match:
                raise UnsupportedSyntax(f"Expressão local não suportada: {text[:70]}")
            self.tokens.append(match.group(1).lower())
            offset = match.end()
        self.index = 0
        self.names = names
        self.structural = structural
        self.atom_depth = 0
        depth = 0
        for value in self.tokens:
            depth += (value == "(") - (value == ")")
            if depth > 40:
                raise UnsupportedSyntax("Expressão excede o limite de 40 níveis de parênteses.")
        if len(self.tokens) > 2_000:
            raise UnsupportedSyntax("Expressão excede o limite de 2.000 tokens.")
        if not structural and len(self.tokens) > 200:
            raise UnsupportedSyntax("Expressão do modelo executável limitada a 200 tokens.")
        self.tree = self._or()
        if self.index != len(self.tokens):
            raise UnsupportedSyntax(f"Expressão local incompleta ou desconhecida: {text[:70]}")

    def _take(self, *options: str) -> str | None:
        if self.index < len(self.tokens) and self.tokens[self.index] in options:
            value = self.tokens[self.index]
            self.index += 1
            return value
        return None

    def _or(self):
        tree = self._and()
        while self._take("or"):
            tree = ("or", tree, self._and())
        return tree

    def _and(self):
        tree = self._compare()
        while self._take("and"):
            tree = ("and", tree, self._compare())
        return tree

    def _compare(self):
        negations = 0
        while self._take("not"):
            negations += 1
            if negations > 40:
                raise UnsupportedSyntax("Expressão excede o limite de 40 negações.")
        tree = self._sum()
        if self._take("is"):
            negate = self._take("not") is not None
            if not self._take("null"):
                raise UnsupportedSyntax("Somente IS [NOT] NULL suportado no modelo local.")
            tree = ("isnotnull" if negate else "isnull", tree)
        else:
            operator = self._take("=", "<>", "<", ">", "<=", ">=")
            tree = (operator, tree, self._sum()) if operator else tree
        for _ in range(negations):
            tree = ("not", tree)
        return tree

    def _sum(self):
        tree = self._product()
        while True:
            operator = self._take("+", "-")
            if not operator:
                return tree
            tree = (operator, tree, self._product())

    def _product(self):
        tree = self._atom()
        while True:
            operator = self._take("*", "/")
            if not operator:
                return tree
            tree = (operator, tree, self._atom())

    def _atom(self):
        self.atom_depth += 1
        if self.atom_depth > 80:
            raise UnsupportedSyntax("Expressão excede o limite de 80 níveis de operações unárias.")
        try:
            return self._atom_inner()
        finally:
            self.atom_depth -= 1

    def _atom_inner(self):
        if self._take("-"):
            return ("negate", self._atom())
        if self._take("+"):
            return self._atom()
        if self._take("("):
            tree = self._or()
            if not self._take(")"):
                raise UnsupportedSyntax("Parênteses não balanceados no modelo local.")
            return tree
        if self.index >= len(self.tokens):
            raise UnsupportedSyntax("Expressão local vazia.")
        value = self.tokens[self.index]
        self.index += 1
        if value == "null":
            return ("constant", None)
        if value in {"true", "false"}:
            return ("constant", value == "true")
        if re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)", value):
            if len(value) > 50:
                raise UnsupportedSyntax("Constante excede 50 caracteres.")
            return ("constant", Decimal(value))
        if self.structural and value[:1] in {"'", '"'}:
            return ("constant", value)
        if self.structural and re.fullmatch(r"[a-z_]\w*(?:\.[a-z_]\w*)?", value):
            if self._take("("):
                arguments = []
                if not self._take(")"):
                    arguments.append(self._or())
                    while self._take(","):
                        arguments.append(self._or())
                    if not self._take(")"):
                        raise UnsupportedSyntax("Argumentos de chamada não suportados ou parênteses não balanceados.")
                return ("opaque_call", value, arguments)
            return ("variable", value)
        if value not in self.names:
            raise UnsupportedSyntax(f"Identificador ou chamada não suportada no modelo local: {value}")
        return ("variable", value)


def _evaluate(tree, environment: dict):
    operator = tree[0]
    if operator == "constant":
        return tree[1]
    if operator == "variable":
        return environment[tree[1]]
    left = _evaluate(tree[1], environment)
    if operator in {"isnull", "isnotnull"}:
        return (left is None) if operator == "isnull" else (left is not None)
    if operator == "negate":
        return None if left is None else -left
    if operator == "not":
        return None if left is None else not left
    right = _evaluate(tree[2], environment)
    if operator == "or":
        return True if left is True or right is True else None if left is None or right is None else bool(left or right)
    if operator == "and":
        return False if left is False or right is False else None if left is None or right is None else bool(left and right)
    if left is None or right is None:
        return None
    if operator == "+":
        return left + right
    if operator == "-":
        return left - right
    if operator == "*":
        return left * right
    if operator == "/":
        return left / right
    if operator == "=":
        return left == right
    if operator == "<>":
        return left != right
    if operator == "<":
        return left < right
    if operator == ">":
        return left > right
    if operator == "<=":
        return left <= right
    if operator == ">=":
        return left >= right
    raise UnsupportedSyntax(f"Operador não suportado: {operator}")


def _compile_model(source: str) -> dict:
    functions = _source_functions(source)
    function = next((item for item in functions if item["name"] == "cad0001_calcula_valor"), None)
    if function is None or "error" in function:
        raise UnsupportedSyntax("cad0001_calcula_valor ausente ou com sintaxe não suportada.")
    if len(function["parameters"]) != 3:
        raise UnsupportedSyntax("O modelo local exige exatamente três parâmetros.")
    statement_count = 0
    def compile_block(items: list[dict]):
        nonlocal statement_count
        for item in items:
            statement_count += 1
            if statement_count > 100:
                raise UnsupportedSyntax("Modelo local limitado a 100 instruções.")
            kind = item["kind"]
            if kind == "let":
                target, expression = re.split(r"=", re.sub(r"^LET\s+", "", item["text"], flags=re.I), maxsplit=1)
                target = target.strip().lower()
                if target not in function["declared"]:
                    raise UnsupportedSyntax("Modelo local aceita apenas atribuições a variáveis declaradas.")
                item["target"] = target
                item["expression"] = _Expression(expression, function["declared"]).tree
            elif kind in {"if", "return"}:
                expression = item["text"] if kind == "if" else re.sub(r"^RETURN\s*", "", item["text"], flags=re.I)
                item["expression"] = _Expression(expression, function["declared"]).tree
                if kind == "if":
                    compile_block(item["yes"])
                    compile_block(item["no"])
            else:
                raise UnsupportedSyntax(f"Modelo local não executa {kind.upper()}.")
    compile_block(function["ast"])
    return function


def _execute_model(function: dict, inputs: list[Decimal | None]):
    environment = {name: None for name in function["declared"]}
    environment.update(zip(function["parameters"], inputs))
    def block(items: list[dict]):
        for item in items:
            kind = item["kind"]
            value = _evaluate(item["expression"], environment)
            if kind == "let":
                environment[item["target"]] = value
            elif kind == "return":
                return True, value
            else:
                returned, result = block(item["yes"] if value else item["no"])
                if returned:
                    return True, result
        return False, None
    with localcontext() as context:
        context.prec = 80
        returned, result = block(function["ast"])
    if not returned:
        raise UnsupportedSyntax("Caminho do modelo local terminou sem RETURN.")
    return result


def _decimal(value, *, nullable: bool = True):
    if value is None or (isinstance(value, str) and value.strip().upper() in {"NULL", "NONE", ""}):
        if nullable:
            return None
        raise ValueError("Resultado esperado obrigatório.")
    if isinstance(value, bool) or len(str(value)) > 50:
        raise ValueError("Informe número decimal finito com até 50 caracteres ou NULL.")
    try:
        number = Decimal(str(value).replace(",", "."))
    except InvalidOperation as error:
        raise ValueError(f"Valor decimal inválido: {value}") from error
    if not number.is_finite() or abs(number.adjusted()) > 30:
        raise ValueError("Informe decimal finito com expoente entre -30 e 30.")
    return number


def _result_text(value) -> str:
    return "NULL" if value is None else format(value, "f") if isinstance(value, Decimal) else str(value)


def _mutations(source: str, function: dict) -> list[dict]:
    mutations = []
    seen = set()
    # Search executable tokens on an offset-preserving mask, then apply edits
    # to the original source. Operators written in comments/strings are inert.
    masked = _mask(source, strings=True)
    def add(start: int, end: int, replacement: str, operator: str, description: str):
        if len(mutations) >= MAX_MUTANTS:
            raise UnsupportedSyntax(f"Mutações excedem o limite de {MAX_MUTANTS} candidatos; reduza a função de cálculo.")
        mutant = source[:start] + replacement + source[end:]
        if mutant == source or mutant in seen:
            return
        seen.add(mutant)
        mutations.append({"id": f"MU{len(mutations) + 1:02d}", "operator": operator, "description": description, "line": _line(source, start), "before": source[start:end], "after": replacement, "source": mutant})
    def walk(items: list[dict]):
        for item in items:
            kind = item["kind"]
            if kind == "let":
                text = masked[item["start"]:item["end"]]
                equal = text.find("=")
                for match in re.finditer(r"[+*/-]", text[equal + 1:]):
                    offset = item["start"] + equal + 1 + match.start()
                    original = match.group()
                    # Unary negation and numeric signs are not AOR sites.
                    prefix = text[equal + 1:equal + 1 + match.start()].rstrip()
                    if original == "-" and (not prefix or prefix[-1] in "(+-*/"):
                        continue
                    replacement = {"*": "+", "+": "-", "-": "+", "/": "*"}[original]
                    add(offset, offset + 1, replacement, "AOR", f"Troca operador aritmético {original} por {replacement}.")
                zero = re.fullmatch(r"\s*(0(?:\.0*)?)\s*", text[equal + 1:])
                if zero:
                    begin = item["start"] + equal + 1 + zero.start(1)
                    end = item["start"] + equal + 1 + zero.end(1)
                    add(begin, end, "1", "CRP", "Troca constante de normalização 0 por 1.")
            elif kind == "if":
                header = masked[item["start"]:item["end"]]
                then = re.search(r"\bTHEN\b", header, re.I)
                condition = header[:then.start()] if then else ""
                null = re.search(r"\bIS\s+(NOT\s+)?NULL\b", condition, re.I)
                if null:
                    add(item["start"] + null.start(), item["start"] + null.end(), "IS NULL" if null.group(1) else "IS NOT NULL", "NCR", "Inverte o predicado de nulidade.")
                    if len(item["yes"]) == 1 and not item["no"] and item["yes"][0]["kind"] == "let":
                        add(item["start"], item["end"], "", "SDL", "Remove a normalização condicional de NULL.")
                for match in re.finditer(r"<>|<=|>=|(?<![<>=])[<>=](?![<>=])", condition):
                    original = match.group()
                    replacement = {"<": "<=", ">": ">=", "<=": "<", ">=": ">", "=": "<>", "<>": "="}[original]
                    add(item["start"] + match.start(), item["start"] + match.end(), replacement, "ROR", f"Troca comparação {original} por {replacement}.")
                walk(item["yes"])
                walk(item["no"])
            elif kind == "return":
                text = masked[item["start"]:item["end"]]
                if not re.fullmatch(r"RETURN\s+0(?:\.0*)?", text, re.I):
                    add(item["start"], item["end"], "RETURN 0", "RVR", "Substitui retorno por zero.")
    walk(function["ast"])
    return mutations


def run_mutation_analysis(source: str, cases: list[dict], manual_equivalents=()) -> dict:
    """Execute original and source mutants in the bounded Decimal model.

    Cases accept {id, inputs:[p1,p2,p3], expected}, or {id,p1,p2,p3,expected}.
    A mutant is killed when it differs from the original on a case whose oracle
    the original passes. Oracle failures remain explicit and do not kill mutants.
    Runtime errors on valid mutants count as kills; compile failures are invalid.
    Equivalence is exclusively a user's manual claim, optionally supplied as
    {mutant_id: justification}; a surviving mutant alone is never equivalent.
    """
    scope = "Modelo local da função cad0001_calcula_valor: Decimal, LET, IF, RETURN, NULL; sem runtime 4GL, banco, precisão DECIMAL(12,2), arredondamento ou execução de código externo."
    result = {"supported": False, "errors": [], "model_scope": scope, "source_sha256": sha256(source.encode("utf-8")).hexdigest(), "original_results": [], "original_failures": [], "mutants": [], "summary": None}
    try:
        original = _compile_model(source)
        if not isinstance(cases, list) or not cases or len(cases) > MAX_CASES:
            raise ValueError("A suíte deve conter entre 1 e 200 casos.")
        normalized = []
        identifiers = set()
        for index, case in enumerate(cases):
            name = str(case.get("id", f"M{index + 1:02d}"))
            if not name or name in identifiers:
                raise ValueError("Cada caso precisa de ID único e não vazio.")
            identifiers.add(name)
            if "inputs" not in case and not all(key in case for key in ("p1", "p2", "p3")):
                raise ValueError(f"Caso {name}: informe inputs ou os três campos p1, p2 e p3.")
            inputs = case.get("inputs", [case.get("p1"), case.get("p2"), case.get("p3")])
            if not isinstance(inputs, (list, tuple)) or len(inputs) != 3:
                raise ValueError(f"Caso {name}: informe exatamente três entradas.")
            if "expected" not in case:
                raise ValueError(f"Caso {name}: resultado esperado obrigatório.")
            normalized.append({"id": name, "inputs": [_decimal(value) for value in inputs], "expected": _decimal(case["expected"])})
        outputs = []
        passing = []
        for case in normalized:
            try:
                output = _execute_model(original, case["inputs"])
                error = None
            except (ArithmeticError, ValueError, TypeError) as problem:
                output, error = None, str(problem)
            passed = error is None and output == case["expected"]
            row = {"id": case["id"], "inputs": [_result_text(value) for value in case["inputs"]], "expected": _result_text(case["expected"]), "actual": _result_text(output), "passed": passed, "error": error}
            result["original_results"].append(row)
            outputs.append(output)
            passing.append(passed)
            if not passed:
                result["original_failures"].append(row)
        manual = dict(manual_equivalents) if isinstance(manual_equivalents, dict) else {str(name): "Equivalência informada manualmente pelo usuário; requer justificativa." for name in manual_equivalents}
        for mutation in _mutations(source, original):
            mutation["killed_by"] = []
            mutation["results"] = []
            try:
                model = _compile_model(mutation["source"])
            except (UnsupportedSyntax, ValueError) as error:
                mutation.update({"status": "invalid", "error": str(error)})
                result["mutants"].append(mutation)
                continue
            for index, case in enumerate(normalized):
                try:
                    actual = _execute_model(model, case["inputs"])
                    error = None
                except (ArithmeticError, ValueError, TypeError) as problem:
                    actual, error = None, str(problem)
                killed = passing[index] and (error is not None or actual != outputs[index])
                if killed:
                    mutation["killed_by"].append(case["id"])
                mutation["results"].append({"case": case["id"], "actual": _result_text(actual), "error": error, "killed": killed, "oracle_valid": passing[index]})
            if mutation["killed_by"]:
                mutation["status"] = "killed"
                if mutation["id"] in manual:
                    mutation["equivalence_rejected"] = "Um caso distingue o mutante do original; a marcação manual não foi aplicada."
            elif mutation["id"] in manual:
                mutation["status"] = "equivalent"
                mutation["equivalence_justification"] = str(manual[mutation["id"]])
                mutation["equivalence_proven"] = False
            else:
                mutation["status"] = "survived"
            result["mutants"].append(mutation)
        counts = {status: sum(mutant["status"] == status for mutant in result["mutants"]) for status in ("killed", "survived", "invalid", "equivalent")}
        denominator = counts["killed"] + counts["survived"]
        score_available = denominator > 0 and any(passing)
        result["summary"] = {"total": len(result["mutants"]), "valid": len(result["mutants"]) - counts["invalid"], **counts, "denominator": denominator, "score": counts["killed"] / denominator if score_available else None, "score_percent": 100 * counts["killed"] / denominator if score_available else None, "formula": f"{counts['killed']} / ({len(result['mutants'])} - {counts['invalid']} - {counts['equivalent']})", "eligible_cases": sum(passing), "oracle_failures": len(result["original_failures"]), "suite_valid": all(passing), "score_scope": "Somente casos em que o original satisfaz o esperado; resultado parcial se houver falhas de oráculo."}
        result["supported"] = True
    except (UnsupportedSyntax, ValueError, TypeError, KeyError, RecursionError) as error:
        result["errors"].append(str(error))
    return result
