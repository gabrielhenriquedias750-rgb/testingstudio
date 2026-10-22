"""Gere o pacote local da sprint 4 sem abrir a interface nem consumir API."""

from __future__ import annotations

import argparse
from pathlib import Path

from audit import load_source
from delivery import acceptance_template, pitch_content, run_validation, validation_markdown
from presentation import delivery_bundle, json_text, pitch_html, pitch_markdown, table_csv


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "cad0001_item_calculo.txt")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "sprint4")
    parser.add_argument("--junit", type=Path, help="XML de uma execução real do pytest para anexar ao pacote.")
    args = parser.parse_args()
    try:
        source = load_source(args.source)
        report = run_validation(source, args.source.name)
        pitch = pitch_content(report)
        acceptance = acceptance_template(report)
        junit = args.junit.read_bytes() if args.junit else None
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=True)
        files = {
            "validacao.json": json_text({"validation": report, "acceptance": acceptance}),
            "validacao.md": validation_markdown(report, acceptance),
            "rastreabilidade.csv": table_csv(report["checks"]),
            "aceitacao.csv": table_csv(acceptance),
            "pitch.html": pitch_html(pitch),
            "pitch.md": pitch_markdown(pitch),
        }
        if report.get("functional"):
            files["funcional_requisitos.csv"] = table_csv(report["functional"]["requirements"])
            files["funcional_casos.csv"] = table_csv(report["functional"]["tests"])
        for name, content in files.items():
            (output / name).write_text(content, encoding="utf-8")
        (output / "testingstudio_sprint4.zip").write_bytes(delivery_bundle(report, pitch, acceptance, junit))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Não foi possível preparar a entrega: {exc}\n")
    print(f"Verificação técnica: {report['summary']['technical_status']}")
    if report.get("functional"):
        print(f"Validação funcional do CAD0001: {report['functional']['summary']['status']}")
    print("Aceitação com usuário: Pendente (nenhum cenário foi aprovado automaticamente).")
    print(f"Fonte SHA-256: {report['source_sha256']}")
    print(f"Pacote: {output / 'testingstudio_sprint4.zip'}")
    return 1 if report["summary"]["technical_status"] == "Reprovado" else 0


if __name__ == "__main__":
    raise SystemExit(main())
