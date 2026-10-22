"""Sprint 4: reproducible local verification and a proposed acceptance/pitch kit.

No network, shell, pytest or legacy runtime is invoked. A local check records
what the program actually verified; it never approves customer acceptance.
Every run computes fresh evidence from its source/suite snapshots.
"""

from __future__ import annotations

from collections import Counter, deque
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import json
import re
from zoneinfo import ZoneInfo

from audit import EPSILON, PARAMETERS, boundary_rows, equivalence_rows, generate_cases, inspect_source, validate_source
from functional_validation import validate_functional_plan
from structural import analyze_source, default_mutation_cases, run_mutation_analysis


SCHEMA_VERSION = "1.0"
STATUSES = ("Aprovado", "Reprovado", "Pendente")
LIMITS = [
    "Esta execução faz verificação técnica local. Aceitação e homologação pelo usuário permanecem manuais.",
    "PCE/AVL é um plano de casos da regra escrita; esses 15 casos não foram executados no runtime 4GL.",
    "A RTM funcional observa casos selecionados no modelo local contra a regra escrita; NULL continua sem oráculo confirmado. O escore de mutação usa uma suíte de caracterização separada.",
    "GFC e Def-Uso analisam o subconjunto 4GL suportado; SQL e CALL são opacos, e viabilidade semântica dos caminhos não é provada.",
    "Mutações executam somente o modelo local Decimal da função de cálculo, sem Informix, banco, transações ou arredondamento DECIMAL(12,2).",
    "Escore de mutação caracteriza a suíte e os operadores desta execução. Não há limiar mínimo de aprovação definido para esta proposta.",
    "Nenhuma suíte pytest, homologação com cliente, teste de usabilidade ou teste de produção é executado por este relatório.",
    "A sprint 4 é uma proposta de pitch e validação baseada no projeto e em referências externas; não foi fornecido um enunciado específico da disciplina.",
]


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str, allow_nan=False)


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _check(identifier: str, requirement: str, method: str, status: str, expected, observed, evidence) -> dict:
    if status not in STATUSES:
        raise ValueError("Estado de validação desconhecido.")
    return {"id": identifier, "requirement": requirement, "method": method, "status": status,
            "expected": expected, "observed": observed, "evidence": evidence}


def _reachable(start: str, adjacency: dict[str, list[str]]) -> set[str]:
    queue, reached = deque([start]), {start}
    while queue:
        for target in adjacency.get(queue.popleft(), []):
            if target not in reached:
                reached.add(target)
                queue.append(target)
    return reached


def _cfg_problems(function: dict) -> list[str]:
    if not function.get("supported"):
        return ["Sintaxe não suportada: " + "; ".join(function.get("errors", []))]
    nodes, edges, metric = function["nodes"], function["edges"], function["metrics"]
    identifiers = {node["id"] for node in nodes}
    problems = []
    if len(identifiers) != len(nodes) or len({edge["id"] for edge in edges}) != len(edges):
        problems.append("IDs de nós/arestas não são únicos.")
    entries = [node["id"] for node in nodes if node["kind"] == "entry"]
    exits = [node["id"] for node in nodes if node["kind"] == "exit"]
    if len(entries) != 1 or len(exits) != 1:
        problems.append("Grafo deve ter uma entrada e uma saída unificadas.")
    forward, backward = {}, {}
    for edge in edges:
        if edge["source"] not in identifiers or edge["target"] not in identifiers:
            problems.append(f"Aresta {edge['id']} referencia nó inexistente.")
        forward.setdefault(edge["source"], []).append(edge["target"])
        backward.setdefault(edge["target"], []).append(edge["source"])
    if len(entries) == len(exits) == 1:
        if _reachable(entries[0], forward) != identifiers or _reachable(exits[0], backward) != identifiers:
            problems.append("Há nó sem caminho da entrada até a saída.")
    decisions = sum(node["kind"] == "if" for node in nodes)
    complexity = len(edges) - len(nodes) + 2
    if not (metric["nodes"] == len(nodes) and metric["edges"] == len(edges)
            and metric["decisions"] == decisions and metric["cyclomatic"] == complexity == decisions + 1):
        problems.append("N/E/V(G) ou igualdade E−N+2=P+1 inconsistente.")
    return problems


def _basis_problems(function: dict) -> tuple[list[str], int]:
    if not function.get("supported"):
        return ["Sem GFC suportado para verificar a base."], 0
    edges = {edge["id"]: edge for edge in function["edges"]}
    indexes = {identifier: index for index, identifier in enumerate(edges)}
    entries = {node["id"] for node in function["nodes"] if node["kind"] == "entry"}
    exits = {node["id"] for node in function["nodes"] if node["kind"] == "exit"}
    pivots, problems = {}, []
    for path in function["basis_paths"]:
        nodes, edge_ids = path["nodes"], path["edges"]
        valid = bool(nodes) and nodes[0] in entries and nodes[-1] in exits and len(edge_ids) == len(nodes) - 1 and len(set(nodes)) == len(nodes)
        vector = 0
        for index, edge_id in enumerate(edge_ids):
            edge = edges.get(edge_id)
            if edge is None or index + 1 >= len(nodes) or (edge["source"], edge["target"]) != (nodes[index], nodes[index + 1]):
                valid = False
            elif edge_id in indexes:
                vector ^= 1 << indexes[edge_id]
        if not valid:
            problems.append(f"{path['id']}: sequência não é um caminho entrada–saída válido.")
            continue
        while vector:
            pivot = vector.bit_length() - 1
            if pivot in pivots:
                vector ^= pivots[pivot]
            else:
                pivots[pivot] = vector
                break
    expected = function["metrics"]["cyclomatic"]
    if len(pivots) != expected or len(function["basis_paths"]) != expected:
        problems.append(f"Base com rank {len(pivots)}, dimensão exigida {expected}.")
    return problems, len(pivots)


def _du_problems(function: dict) -> list[dict]:
    if not function.get("supported"):
        return [{"problem": "Função não suportada; pares DU não verificados."}]
    nodes = {node["id"]: node for node in function["nodes"]}
    edges = {edge["id"]: edge for edge in function["edges"]}
    connections = {(edge["source"], edge["target"]) for edge in edges.values()}
    problems = []
    for pair in function["def_use"]:
        origin, use, variable = pair["definition"], pair["use"], pair["variable"]
        path = pair["path"]
        valid = origin in nodes and use in nodes and bool(path)
        valid = valid and variable in nodes[origin]["defs"] and variable in nodes[use]["uses"]
        if pair["use_type"] == "p-use":
            edge = edges.get(pair.get("edge"))
            valid = valid and len(path) >= 2 and edge is not None
            valid = valid and edge["source"] == use and edge["target"] == path[-1] and path[-2] == use and pair.get("branch") == edge["label"]
            to_use = path[:-1]
        elif pair["use_type"] == "c-use":
            to_use = path
            valid = valid and pair.get("edge") is None
        else:
            to_use, valid = path, False
        valid = valid and bool(to_use) and to_use[0] == origin and to_use[-1] == use
        valid = valid and all(identifier in nodes for identifier in path)
        valid = valid and all((first, second) in connections for first, second in zip(path, path[1:]))
        valid = valid and all(variable not in nodes[identifier]["defs"] for identifier in to_use[1:-1])
        if not valid:
            problems.append({"variable": variable, "definition": origin, "use": use, "path": path,
                             "problem": "Par DU/caminho inconsistente ou com redefinição intermediária."})
    return problems


def run_validation(source: str, source_name: str = "Editor", cases: list[dict] | None = None, *, selected_functional_ids=None) -> dict:
    """Compute fresh technical checks and pending manual acceptance obligations.

    Invalid sources raise ValueError for a friendly UI message. This function
    does not consume prior Sprint 1/3 reports or infer acceptance from them.
    """
    validate_source(source)
    functional = validate_functional_plan(source, selected_functional_ids)
    cases = deepcopy(default_mutation_cases() if cases is None else cases)
    try:
        suite_json = _json(cases)
    except (ValueError, TypeError) as error:
        raise ValueError("A suíte deve ser serializável e conter valores decimais finitos.") from error
    cases = json.loads(suite_json)
    digest, suite_digest = _hash(source), _hash(suite_json)
    created_at = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="microseconds")
    report_id = "VAL-" + _hash(_json([SCHEMA_VERSION, digest, suite_digest, functional["selection_sha256"], created_at]))[:20]
    structural = analyze_source(source)
    mutation = run_mutation_analysis(source, cases)
    checks = []
    provenance_ok = digest == structural["source_sha256"] == mutation["source_sha256"] == functional["source_sha256"]
    checks.append(_check("S4-01", "Vincular evidências à fonte e à suíte desta execução", "SHA-256 de snapshots atuais; sem reutilizar relatórios anteriores.",
                         "Aprovado" if provenance_ok else "Reprovado", "Hashes da fonte iguais em todas as análises; suíte identificada.",
                         {"source_sha256": digest, "suite_sha256": suite_digest, "source_characters": len(source)},
                         {"report_id": report_id, "analysis_source_sha256": structural["source_sha256"], "mutation_source_sha256": mutation["source_sha256"],
                          "functional_source_sha256": functional["source_sha256"], "functional_selection_sha256": functional["selection_sha256"]}))

    planned = generate_cases()
    partitions, boundaries = equivalence_rows(), boundary_rows()
    plan_ok = len(planned) == 15 and EPSILON == Decimal("0.01") and len({row["ID"] for row in planned}) == 15
    plan_ok = plan_ok and all({row["Ponto"] for row in planned if row["Parâmetro"] == parameter} == {"On-Point", "Off-Point", "Interior", "Exterior", "Nulo"} for parameter in PARAMETERS)
    checks.append(_check("S1-01", "Preservar e identificar o plano PCE/AVL da sprint 1", "Geração local do plano da regra escrita; nenhum CT executado no 4GL.",
                         "Aprovado" if plan_ok else "Reprovado", "15 casos planejados: cinco pontos para cada um dos três parâmetros; ε=0,01.",
                         {"planned_cases": len(planned), "epsilon": str(EPSILON), "executed_4gl_cases": 0, "classification": "Plano de testes"},
                         {"cases": planned, "partitions": partitions, "boundaries": boundaries, "source_inspection": inspect_source(source)}))

    cfg_rows, basis_rows, du_rows, anomaly_rows = [], [], [], []
    for function in structural["functions"]:
        cfg_errors = _cfg_problems(function)
        basis_errors, basis_rank = _basis_problems(function)
        du_errors = _du_problems(function)
        cfg_rows.append({"function": function["name"], "supported": function["supported"], "metrics": function["metrics"], "problems": cfg_errors})
        basis_rows.append({"function": function["name"], "rank_verified": basis_rank, "path_count": len(function["basis_paths"]), "problems": basis_errors})
        du_rows.append({"function": function["name"], "complete": function.get("def_use_complete", False), "pairs": len(function["def_use"]), "problems": du_errors})
        anomaly_rows.extend({"function": function["name"], **row} for row in function["anomalies"])
    cfg_ok = bool(cfg_rows) and all(not row["problems"] for row in cfg_rows)
    basis_ok = bool(basis_rows) and all(not row["problems"] for row in basis_rows)
    du_ok = bool(du_rows) and all(not row["problems"] for row in du_rows)
    du_complete = all(row["complete"] for row in du_rows)
    checks.append(_check("S2-01", "GFC suportado e complexidade coerente em todas as funções", "Recontagem dos nós/arestas/decisões e conectividade entrada–saída.",
                         "Aprovado" if cfg_ok else "Reprovado", "V(G)=E−N+2=P+1 em cada função, com uma entrada e uma saída.",
                         {"functions": len(cfg_rows), "consistent": sum(not row["problems"] for row in cfg_rows)}, cfg_rows))
    checks.append(_check("S2-02", "Base de caminhos estruturalmente válida e independente", "Verificação de cada aresta e rank GF(2) recalculado sobre as incidências.",
                         "Aprovado" if basis_ok else "Reprovado", "Caminhos entrada–saída válidos, rank e quantidade iguais a V(G).", basis_rows,
                         {"functions": basis_rows, "semantic_feasibility": "Não provada; requer escolha de entradas viáveis."}))
    checks.append(_check("S3-01", "Pares Def-Uso íntegros e caminhos sem redefinição", "Conferência dos nós de definição/uso, arestas p-use e caminhos livres de redefinições intermediárias.",
                         "Reprovado" if not du_ok else "Aprovado" if du_complete else "Pendente",
                         "Tabela completa de pares do modelo; c-use em nó e p-use em aresta, com caminho DU válido.", du_rows,
                         {"functions": du_rows, "coverage": "Integridade estática; cobertura por execução não foi medida."}))

    original_rows = mutation.get("original_results", [])
    original_failures = mutation.get("original_failures", [])
    original_ok = mutation["supported"] and len(original_rows) == len(cases) and all(row["passed"] for row in original_rows)
    original_status = "Aprovado" if original_ok else "Reprovado" if mutation["supported"] else "Pendente"
    checks.append(_check("S3-02", "Original do modelo satisfaz a suíte informada", "Execução fresca do modelo local Decimal contra o esperado de cada caso.", original_status,
                         "Original aprova todos os casos desta suíte; divergências permanecem explícitas.",
                         {"supported": mutation["supported"], "cases": len(cases), "passed": sum(row["passed"] for row in original_rows), "failed": len(original_failures), "errors": mutation["errors"]},
                         {"suite_sha256": suite_digest, "results": original_rows, "failures": original_failures, "scope": mutation["model_scope"]}))

    mutation_summary = mutation.get("summary")
    mutation_ok, mutation_status = False, "Pendente"
    score_recomputed = None
    if mutation["supported"] and mutation_summary is not None:
        counts = Counter(item["status"] for item in mutation["mutants"])
        denominator = counts["killed"] + counts["survived"]
        eligible = sum(row["passed"] for row in original_rows)
        score_recomputed = counts["killed"] / denominator if denominator and eligible else None
        mutation_ok = mutation_summary["total"] == len(mutation["mutants"]) and mutation_summary["valid"] == len(mutation["mutants"]) - counts["invalid"]
        mutation_ok = mutation_ok and all(mutation_summary[key] == counts[key] for key in ("killed", "survived", "invalid", "equivalent"))
        mutation_ok = mutation_ok and mutation_summary["denominator"] == denominator and mutation_summary["score"] == score_recomputed
        mutation_status = "Reprovado" if not mutation_ok else "Aprovado" if original_ok and score_recomputed is not None and counts["survived"] == 0 else "Pendente"
    checks.append(_check("S3-03", "Escore de mutação reproduzível e sobreviventes identificados", "Recontagem de mortos/vivos/inválidos/equivalentes; sem estabelecer escore mínimo da disciplina.", mutation_status,
                         "MS=mortos/(total−inválidos−equivalentes); revisar sobreviventes e casos com oráculo divergente.",
                         {"summary": mutation_summary, "score_recomputed": score_recomputed, "accounting_consistent": mutation_ok},
                         {"survivors": [item["id"] for item in mutation["mutants"] if item["status"] == "survived"],
                          "invalid": [item["id"] for item in mutation["mutants"] if item["status"] == "invalid"],
                          "killed_by": {item["id"]: item["killed_by"] for item in mutation["mutants"] if item["status"] == "killed"},
                          "errors": mutation["errors"], "model_scope": mutation["model_scope"]}))

    undefined = [row for row in anomaly_rows if row["kind"] == "use-without-definition"]
    checks.append(_check("S3-04", "Revisar anomalias estáticas com contexto do programa", "Separação de uso sem definição e definições sem uso/sobrescritas evidenciadas.",
                         "Reprovado" if undefined else "Pendente" if anomaly_rows else "Aprovado",
                         "Sem uso local sem definição; demais achados recebem revisão humana, inclusive efeitos globais e SQL opaco.",
                         {"anomalies": len(anomaly_rows), "uses_without_definition": len(undefined), "review_required": bool(anomaly_rows)}, anomaly_rows))
    checks.append(_check("S4-02", "Validar uso pretendido com avaliador e registrar aceite", "Roteiro manual de demonstração, observação e registro em ambiente de uso.", "Pendente",
                         "Avaliador identificado executa cenários e registra resultado, data, fonte e relatório vinculados.",
                         "Nenhuma homologação ou sessão com usuário foi executada automaticamente.",
                         {"report_id": report_id, "source_sha256": digest, "manual_acceptance": "Pendente", "pytest_execution": "Não executada por esta validação"}))

    counts = Counter(check["status"] for check in checks)
    technical = [check for check in checks if check["id"] != "S4-02"]
    technical_status = "Reprovado" if any(check["status"] == "Reprovado" for check in technical) else "Pendente" if any(check["status"] == "Pendente" for check in technical) else "Aprovado"
    summary = {"status": "Reprovado" if counts["Reprovado"] else "Pendente", "technical_status": technical_status,
               "acceptance_status": "Pendente", "total": len(checks), "approved": counts["Aprovado"], "failed": counts["Reprovado"], "pending": counts["Pendente"],
               "scope": "Verificação técnica local com aceitação manual pendente; sem homologação automática."}
    return {"schema_version": SCHEMA_VERSION, "report_id": report_id, "created_at": created_at,
            "source_name": str(source_name), "source": source, "source_sha256": digest,
            "cases": cases, "suite_sha256": suite_digest, "checks": checks, "summary": summary,
            "structural": structural, "structural_summary": cfg_rows, "mutation": mutation,
            "functional": functional,
            "limits": LIMITS.copy()}


def acceptance_template(report: dict | None = None) -> list[dict]:
    """Return editable manual scenarios, all pending and tied to an optional run."""
    scenarios = [
        ("AC-01", "Rastrear fonte, suíte e relatório", "Avaliador da disciplina",
         ["Abrir o arquivo fornecido e gerar uma validação.", "Conferir nome, fonte exportada, SHA-256 e identificação do relatório.", "Alterar o fonte e gerar outra execução; comparar os vínculos."],
         "Cada execução registra seus próprios snapshots e hashes; resultados anteriores permanecem identificados."),
        ("AC-02", "Explicar caixa-branca usando o grafo", "Pessoa desenvolvedora ou testadora",
         ["Selecionar a função de cálculo e contar decisões, nós e arestas no GFC.", "Conferir V(G)=E−N+2=P+1 e percorrer os caminhos da base.", "Adicionar um IF suportado e recalcular."],
         "GFC, contagens e base acompanham o fonte; viabilidade semântica dos caminhos é discutida explicitamente."),
        ("AC-03", "Inspecionar Def-Uso e redefinições", "Pessoa testadora",
         ["Escolher variável, definição, c-use ou p-use e seguir o caminho DU.", "Inserir uma redefinição e recalcular os pares.", "Examinar e justificar as anomalias com o contexto do programa."],
         "A redefinição interrompe o vínculo da definição anterior; p-use aponta uma aresta e anomalias têm evidência."),
        ("AC-04", "Avaliar a suíte por mutação", "Pessoa testadora",
         ["Executar a suíte e conferir os resultados do original.", "Inspecionar um mutante e o caso que o distinguiu.", "Usar uma suíte fraca, observar sobreviventes e conferir o denominador do escore."],
         "Mortos e sobreviventes derivam de execuções do modelo local; oráculos divergentes são visíveis e equivalência exige justificativa manual."),
        ("AC-05", "Confirmar a regra de negócio de NULL e negativos", "Responsável pela regra de negócio",
         ["Comparar a regra escrita, o plano da sprint 1 e o comportamento do TXT fornecido.", "Definir o resultado esperado para NULL e entradas negativas.", "Registrar decisão e revisar a suíte vinculada à nova execução."],
         "O responsável define o contrato aceito; a equipe registra divergências e não confunde caracterização do código com conformidade à regra."),
        ("AC-06", "Validar a demonstração no ambiente pretendido", "Avaliador ou usuário convidado",
         ["Abrir o aplicativo no navegador do ambiente de apresentação.", "Percorrer fonte, PCE/AVL, GFC, Def-Uso, mutação e exportação de evidências.", "Apresentar o pitch e registrar dúvidas, falhas e decisão do avaliador.", "Identificar separadamente a necessidade de ensaios no runtime e banco 4GL."],
         "O avaliador registra a experiência e limitações observadas; qualquer aceite indica explicitamente seu ambiente e escopo."),
    ]
    return [{"id": identifier, "objective": objective, "profile": profile, "steps": steps,
             "expected": expected, "status": "Pendente", "observed": "", "reviewer": "", "executed_at": "",
             "source_sha256": report["source_sha256"] if report else "", "report_id": report["report_id"] if report else ""}
            for identifier, objective, profile, steps, expected in scenarios]


def acceptance_summary(report: dict | None, records=()) -> dict:
    """Summarize current, signed manual claims without mutating the run snapshot.

    Only known scenarios linked to this exact source and report are eligible.
    Approval/rejection requires reviewer and observed evidence. The last record
    for an ID wins, even if that latest record is stale, unsigned or pending.
    """
    known = {record["id"] for record in acceptance_template(report)}
    latest = {}
    unknown = 0
    for record in records:
        if not isinstance(record, dict) or record.get("id") not in known:
            unknown += 1
            continue
        latest[record["id"]] = record
    counts = Counter()
    for identifier in known:
        record = latest.get(identifier, {})
        linked = bool(report) and record.get("source_sha256") == report["source_sha256"] and record.get("report_id") == report["report_id"]
        signed = bool(str(record.get("reviewer") or "").strip()) and bool(str(record.get("observed") or "").strip())
        declared = record.get("status", "Pendente")
        status = declared if linked and signed and declared in {"Aprovado", "Reprovado"} else "Pendente"
        counts[status] += 1
    status = "Reprovado" if counts["Reprovado"] else "Aprovado" if counts["Aprovado"] == len(known) else "Pendente"
    return {"status": status, "total": len(known), "approved": counts["Aprovado"], "failed": counts["Reprovado"], "pending": counts["Pendente"],
            "source_sha256": report["source_sha256"] if report else None, "report_id": report["report_id"] if report else None,
            "unknown_records": unknown, "scope": "Declaração manual vinculada a esta execução; sem homologação automática."}


def _md(value) -> str:
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _fence(value: str, language: str = "") -> str:
    longest = max((len(match.group()) for match in re.finditer(r"`+", value)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{language}\n{value}\n{fence}"


def validation_markdown(report: dict, acceptance_records=()) -> str:
    """Export readable checks and manual observations without granting acceptance."""
    lines = ["# TestingStudio Web — validação e aceite proposto", f"Relatório: `{report['report_id']}`",
             f"Gerado em: {report['created_at']}", f"Fonte: {_md(report['source_name'])}",
             f"SHA-256 do fonte: `{report['source_sha256']}`", f"SHA-256 da suíte: `{report['suite_sha256']}`",
             report["summary"]["scope"], "## Resultado técnico e estado inicial da execução", _fence(_json(report["summary"]), "json")]
    table = ["| ID | Requisito | Estado | Método |", "| --- | --- | --- | --- |"]
    table.extend(f"| {check['id']} | {_md(check['requirement'])} | {check['status']} | {_md(check['method'])} |" for check in report["checks"])
    lines.append("\n".join(table))
    for check in report["checks"]:
        lines.extend([f"## {check['id']} — {check['requirement']}", f"Estado: **{check['status']}**",
                      "Esperado: " + _md(check["expected"]), "Observado:", _fence(_json(check["observed"]), "json"),
                      "Evidência:", _fence(_json(check["evidence"]), "json")])
    functional = report.get("functional")
    if functional:
        lines.extend(["## Conformidade funcional do CAD0001 — RTM", functional["scope"],
                      "Este veredito trata a regra de negócio no modelo local. Ele é separado das checagens técnicas da ferramenta, do escore de caracterização por mutação e da declaração manual de aceite.",
                      _fence(_json(functional["summary"]), "json"),
                      f"SHA-256 da seleção funcional: `{functional['selection_sha256']}`"])
        forward = ["| Requisito | Descrição | Casos planejados | PASS | FAIL | Pendentes | Estado |", "| --- | --- | --- | --- | --- | --- | --- |"]
        forward.extend(f"| {row['id']} | {_md(row['description'])} | {', '.join(row['planned_cases'])} | {row['passed']} | {row['failed']} | {row['pending']} | {row['status']} |" for row in functional["requirements"])
        lines.extend(["### Rastreabilidade requisito → casos", "\n".join(forward)])
        inverse = ["| Caso | Cenário | Requisitos | Esperado | Observado | Estado | Motivo |", "| --- | --- | --- | --- | --- | --- | --- |"]
        inverse.extend(f"| {row['id']} | {_md(row['scenario'])} | {', '.join(row['requirements'])} | {_md(row['expected'])} | {_md(row['actual'] if row['actual'] is not None else 'Não observável / não executado')} | {row['status']} | {_md(row['reason'])} |" for row in functional["tests"])
        lines.extend(["### Rastreabilidade caso → requisitos", "\n".join(inverse)])
    lines.extend(["## Suíte desta execução", _fence(_json(report["cases"]), "json"),
                  "## Aceitação manual", "Os registros abaixo são declarações manuais. A verificação local não confirma que os cenários foram executados nem concede homologação."])
    records = deepcopy(list(acceptance_records)) if acceptance_records else acceptance_template(report)
    manual = acceptance_summary(report, records)
    lines.extend(["Estado atual da aceitação, conforme declarações manuais vinculadas a este relatório:", _fence(_json(manual), "json")])
    for record in records:
        linked = record.get("source_sha256") == report["source_sha256"] and record.get("report_id") == report["report_id"]
        lines.extend([f"### {_md(record.get('id', 'Sem ID'))} — {_md(record.get('objective', 'Cenário manual'))}",
                      f"Vínculo com esta execução: {'Correspondente' if linked else 'Ausente ou diferente; revisar antes de aceitar'}.",
                      _fence(_json(record), "json")])
    lines.extend(["## Limitações", *("- " + limitation for limitation in report["limits"]),
                  "## Snapshot do fonte analisado", _fence(report["source"], "4gl")])
    return "\n\n".join(lines) + "\n"


def pitch_content(report: dict | None = None, acceptance_records=()) -> dict:
    """Provide six editable proposed slides; measured claims require a fresh run."""
    manual = acceptance_summary(report, acceptance_records)
    if report:
        functions = report["structural"]["functions"]
        measured = f"{sum(item['supported'] for item in functions)}/{len(functions)} funções com GFC suportado; relatório {report['report_id']}."
        summary = report["mutation"].get("summary")
        mutation = (f"Modelo local: {summary['killed']} mortos, {summary['survived']} sobreviventes e {summary['invalid']} inválidos."
                    if summary else "Mutações indisponíveis nesta fonte; revisar os erros do relatório.")
        original = f"Original: {sum(row['passed'] for row in report['mutation']['original_results'])}/{len(report['cases'])} casos aprovados contra o esperado informado."
        evidence = [measured, original, mutation, f"Estado técnico: {report['summary']['technical_status']}; aceitação manual: {manual['status']} (declaração manual)."]
        functional = report.get("functional")
        if functional:
            functional_summary = functional["summary"]
            functional_evidence = (f"Conformidade funcional CAD0001: {functional_summary['status']}; {functional_summary['passed']} PASS, "
                                   f"{functional_summary['failed']} FAIL e {functional_summary['pending']} pendentes, "
                                   f"com {functional_summary['executed']}/{functional_summary['total']} casos executados no modelo local.")
            evidence.insert(1, functional_evidence)
            functional_speech = (f"Na RTM funcional da regra escrita, o veredito é {functional_summary['status']}: "
                                 f"{functional_summary['passed']} casos passaram, {functional_summary['failed']} falharam e {functional_summary['pending']} ficaram pendentes. "
                                 f"Foram executados {functional_summary['executed']} dos {functional_summary['total']} casos no modelo local. "
                                 "NULL permanece sem oráculo confirmado. Esses resultados de conformidade são separados da suíte de caracterização usada na mutação. ")
        else:
            functional_speech = "Não há RTM funcional anexada a este relatório; a conformidade à regra escrita não foi medida nesta evidência. "
        provenance = f"A demonstração usa o relatório {report['report_id']}, gerado em {report['created_at']}. Os hashes da fonte e da suíte estão disponíveis para conferência."
        original_passed = sum(row["passed"] for row in report["mutation"]["original_results"])
        if summary:
            score = "não calculável nesta execução" if summary["score"] is None else f"{summary['score']:.2%}"
            evidence_speech = (
                f"Nesta execução, {sum(item['supported'] for item in functions)} de {len(functions)} funções têm GFC suportado. "
                + functional_speech +
                f"O original do modelo local aprovou {original_passed} dos {len(report['cases'])} casos contra o esperado informado. "
                f"Dos {summary['total']} mutantes gerados, {summary['killed']} foram mortos, {summary['survived']} sobreviveram, "
                f"{summary['invalid']} foram inválidos e {summary['equivalent']} foram declarados equivalentes. O escore é {score}. "
                f"O estado técnico é {report['summary']['technical_status']}. O estado da aceitação é {manual['status']}, conforme declaração manual vinculada a este relatório. "
                "Esses números descrevem esta fonte, esta suíte e os operadores aplicados ao modelo local. "
                "Vamos usar os sobreviventes, divergências de oráculo e anomalias para orientar a revisão."
            )
        else:
            evidence_speech = (
                f"Nesta execução, {sum(item['supported'] for item in functions)} de {len(functions)} funções têm GFC suportado. "
                + functional_speech +
                "A análise de mutação ficou indisponível para esta fonte; os motivos estão registrados no relatório. "
                f"O estado técnico é {report['summary']['technical_status']}. O estado da aceitação é {manual['status']}, conforme declaração manual vinculada a este relatório. "
                "Vamos revisar essa limitação antes de apresentar um escore ou concluir sobre a suíte."
            )
    else:
        evidence = ["Gerar uma validação atual para apresentar contagens, resultados do original e escore.", "Nenhuma execução foi anexada a esta proposta de pitch.", "Aceitação manual pendente."]
        provenance = "Ainda não há uma execução vinculada a este roteiro; vou gerar o relatório com a fonte e a suíte demonstradas."
        evidence_speech = (
            "Ainda não anexamos uma execução a este roteiro, por isso não apresentamos contagens nem escore como resultados concluídos. "
            "Vamos gerar a validação com a fonte e a suíte que serão demonstradas e mostrar os resultados do original, os mutantes e as pendências. "
            "Cada número ficará vinculado ao identificador do relatório e aos hashes correspondentes. A aceitação manual permanece pendente."
        )
    slides = [
        {"title": "O problema: transformar código em evidência de teste", "duration_seconds": 35,
         "bullets": ["Regras escritas e implementação podem divergir, inclusive para NULL e negativos.", "Planejar casos, percorrer caminhos e revisar usos exige rastreabilidade.", "O laboratório trabalha com o CAD0001 fornecido."],
         "speaker_notes": "Ao analisar um sistema legado, precisamos entender o que a regra pede e o que o código faz. No CAD0001, NULL e valores negativos ajudam a mostrar essa diferença. Nosso desafio é transformar essas dúvidas em casos, caminhos e evidências que outra pessoa consiga conferir. O TestingStudio Web reúne esse trabalho em um laboratório com resultados ligados ao fonte analisado."},
        {"title": "Público e proposta do TestingStudio Web", "duration_seconds": 35,
         "bullets": ["Público proposto: estudantes, docentes e pessoas testadoras de sistemas legados.", "Reunir PCE/AVL, GFC, complexidade, Def-Uso e mutação no mesmo fluxo.", "Manter fonte, suíte, evidências e limites identificados em cada execução."],
         "speaker_notes": "Nós propomos o TestingStudio Web para apoiar o aprendizado e a revisão de testes em sistemas legados. Nosso público inicial são estudantes, docentes e pessoas testadoras; essa é uma hipótese que queremos avaliar com usuários. A proposta reúne planejamento de caixa-preta, análise estrutural e mutação, mantendo fonte, suíte e evidência identificados. Queremos verificar se esse fluxo ajuda o avaliador a compreender e revisar cada resultado."},
        {"title": "Demonstração em quatro passos", "duration_seconds": 50,
         "bullets": ["1. Carregar o TXT e observar o plano PCE/AVL da regra escrita.", "2. Escolher uma função, conferir o GFC e calcular V(G).", "3. Seguir um caminho Def-Uso e mostrar o efeito de uma redefinição.", "4. Executar a suíte local, inspecionar um mutante e exportar a evidência."],
         "speaker_notes": "Vou demonstrar o fluxo em quatro passos. Primeiro, carrego o TXT e mostro o plano PCE/AVL: são quinze casos planejados da regra escrita, sem afirmar que foram executados no legado. Depois, escolho uma função e confiro seu grafo, as decisões e a complexidade. Em seguida, sigo uma definição até um uso e observo como uma nova atribuição muda esse vínculo. Por último, executo a suíte no modelo local, inspeciono um mutante e exporto as evidências. " + provenance},
        {"title": "Evidências disponíveis nesta execução", "duration_seconds": 45,
         "bullets": evidence,
         "speaker_notes": evidence_speech},
        {"title": "Validação e limites do resultado", "duration_seconds": 40,
         "bullets": ["Checagens locais conferem hashes, grafos, base, Def-Uso, suíte e contabilização de mutantes.", "Cenários manuais avaliam compreensão, uso no navegador e aderência à regra de negócio.", "Runtime Informix, banco, transações e homologação não foram exercitados por este modelo."],
         "speaker_notes": "As checagens locais conferem rastreabilidade, estrutura dos grafos, independência da base, integridade dos pares Def-Uso e resultados do modelo de mutação. A aceitação de uso se apoia nos registros de uma pessoa avaliadora, que observa a compreensão das evidências e a realização dos cenários no navegador. "
         + f"Nesta apresentação, o estado declarado manualmente é {manual['status']}. "
         + "O modelo não exercita Informix, banco ou transações. Qualquer aceite precisa registrar o ambiente, a fonte, a suíte e o escopo efetivamente avaliados."},
        {"title": "Pedido e próximo passo", "duration_seconds": 35,
         "bullets": ["Propor uma sessão de demonstração com docente ou colega avaliador.", "Pedir confirmação do contrato para NULL e negativos e observações sobre a clareza das evidências.", "Registrar o aceite ou os ajustes solicitados e repetir a validação na fonte revisada."],
         "speaker_notes": "Nosso pedido é realizar uma sessão de demonstração com docente ou colega avaliador. Queremos confirmar o contrato para NULL e negativos, observar a clareza das evidências e registrar os ajustes necessários. Ao final, o avaliador poderá indicar o aceite no escopo observado ou solicitar mudanças. Vamos incorporar esse retorno e repetir a validação na fonte revisada. Este roteiro é uma proposta e poderá ser ajustado ao enunciado específico quando ele estiver disponível."},
    ]
    return {"title": "TestingStudio Web — proposta de pitch e validação", "editable": True, "proposal": True,
            "description": "Roteiro proposto de aproximadamente quatro minutos; conteúdo editável e resultados vinculados à execução.",
            "duration_seconds": sum(slide["duration_seconds"] for slide in slides), "slides": slides,
            "report_id": report["report_id"] if report else None, "source_sha256": report["source_sha256"] if report else None,
            "acceptance": manual,
            "limits": LIMITS.copy()}
