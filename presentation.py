"""Exportações portáteis da entrega, sem dependências de rede ou JavaScript externo."""

from __future__ import annotations

import csv
import html
import io
import json
from zipfile import ZipFile, ZIP_DEFLATED

from delivery import validation_markdown


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def pitch_markdown(pitch: dict) -> str:
    lines = [f"# {pitch['title']}", pitch["description"],
             f"Duração proposta: {pitch['duration_seconds'] // 60} minutos. Ajuste ao tempo informado pela disciplina."]
    if pitch.get("report_id"):
        lines += [f"Relatório: `{pitch['report_id']}`", f"SHA-256 do fonte: `{pitch['source_sha256']}`"]
    for index, slide in enumerate(pitch["slides"], 1):
        lines += [f"## {index}. {slide['title']} ({slide['duration_seconds']} s)",
                  "\n".join(f"- {item}" for item in slide["bullets"]),
                  "**Fala sugerida:** " + slide["speaker_notes"]]
    lines += ["## Limites", *pitch.get("limits", []), "## Referências",
              "- [Sebrae RN: Pitch](https://blog.rn.sebrae.com.br/pitch/)",
              "- [NASA: Product Validation](https://www.nasa.gov/reference/5-4-product-validation/)"]
    return "\n\n".join(lines) + "\n"


def pitch_html(pitch: dict) -> str:
    """Slides offline, com navegação por teclado e impressão de todos os slides."""
    escape = lambda value: html.escape(str(value), quote=True)
    total = len(pitch["slides"])
    provenance = (f"Relatório: {pitch['report_id']} · SHA-256: {pitch['source_sha256']}"
                  if pitch.get("report_id") else "Proposta sem execução anexada")
    sections = []
    for index, slide in enumerate(pitch["slides"], 1):
        items = "".join(f"<li>{escape(item)}</li>" for item in slide["bullets"])
        sections.append(
            f'<section class="slide" aria-label="Slide {index} de {total}">'
            f'<div class="eyebrow">TESTINGSTUDIO WEB <span>SPRINT 04 · {index:02d}/{total:02d}</span></div>'
            f'<h1>{escape(slide["title"])}</h1><ul>{items}</ul>'
            f'<details><summary>Fala sugerida · {slide["duration_seconds"]} segundos</summary>'
            f'<p>{escape(slide["speaker_notes"])}</p></details>'
            f'<footer>Entrega proposta · Evidências locais · {index}/{total}<br>{escape(provenance)}</footer></section>'
        )
    return """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>TestingStudio Web · Pitch</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#102e36;color:#16343b;font:clamp(16px,2vw,26px)/1.55 system-ui,sans-serif}
.slide{max-width:1280px;min-height:90vh;margin:3vh auto;padding:5vw;background:#f6f8f5;border-radius:20px;position:relative;border-top:12px solid #79c9ad}
.eyebrow{font-size:.6em;letter-spacing:.13em;color:#477469;display:flex;justify-content:space-between;gap:1em}
h1{font-size:clamp(30px,4.8vw,64px);line-height:1.1;letter-spacing:-.04em;margin:.9em 0 .7em;max-width:1050px}
ul{padding-left:1.3em;max-width:1050px}li{margin:.65em 0}li::marker{color:#128578}
details{font-size:.65em;border-top:1px solid #d8e4df;padding-top:1em;margin-top:2em}summary{cursor:pointer;color:#38675d}
footer{font-size:.5em;letter-spacing:.08em;color:#648078;margin-top:2em;overflow-wrap:anywhere}
nav{position:sticky;bottom:0;display:flex;justify-content:center;gap:12px;padding:12px;background:#102e36;color:white;font-size:14px;align-items:center}
button{font:inherit;color:#102e36;background:#a8e4c8;border:0;border-radius:7px;padding:9px 18px;cursor:pointer}button:disabled{opacity:.45}
.presenting .slide{display:none}.presenting .slide.active{display:block}
@media print{body{background:white;font-size:18px}.slide,.presenting .slide{display:block!important;border-radius:0;min-height:0;break-after:page;margin:0;padding:20mm;box-shadow:none;border-top:5px solid #128578}nav,details{display:none}h1{font-size:36px}}
</style></head><body>""" + "".join(sections) + """
<nav aria-label="Navegação da apresentação"><button id="prev">← Anterior</button><span id="position"></span><button id="next">Próximo →</button><button id="all">Ver todos</button><button onclick="window.print()">Imprimir / PDF</button></nav>
<script>
const slides=Array.from(document.querySelectorAll('.slide'));let current=0,showAll=false;
function show(){document.body.classList.toggle('presenting',!showAll);slides.forEach((s,i)=>s.classList.toggle('active',i===current));document.querySelector('#position').textContent=(current+1)+' / '+slides.length;document.querySelector('#prev').disabled=current===0;document.querySelector('#next').disabled=current===slides.length-1;document.querySelector('#all').textContent=showAll?'Apresentar':'Ver todos';}
function move(step){current=Math.max(0,Math.min(slides.length-1,current+step));showAll=false;show();window.scrollTo(0,0);}
document.querySelector('#prev').onclick=()=>move(-1);document.querySelector('#next').onclick=()=>move(1);document.querySelector('#all').onclick=()=>{showAll=!showAll;show();};
document.addEventListener('keydown',e=>{if(e.key==='ArrowRight'){e.preventDefault();move(1);}if(e.key==='ArrowLeft'){e.preventDefault();move(-1);}});show();
</script></body></html>"""


def table_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    buffer = io.StringIO(newline="")
    fields = list(dict.fromkeys(key for row in rows for key in row))
    writer = csv.DictWriter(buffer, fieldnames=fields, delimiter=";")
    writer.writeheader()
    for row in rows:
        # CSV exportado será aberto em planilhas: texto não se torna fórmula.
        clean = {}
        for key, value in row.items():
            value = json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list)) else str(value if value is not None else "")
            clean[key] = "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value
        writer.writerow(clean)
    return buffer.getvalue()


def delivery_bundle(report: dict, pitch: dict, acceptance: list[dict], junit: bytes | None = None) -> bytes:
    """Pacote autocontido do snapshot analisado, sem arquivos de configuração."""
    files = {
        "LEIA-ME.md": (
            "# TestingStudio Web — Sprint 4\n\nEntrega proposta a partir de pesquisa, autorizada pelo usuário; não é um enunciado oficial da disciplina.\n\n"
            f"Fonte: {report['source_name']}\n\nSHA-256: {report['source_sha256']}\n\nExecução: {report['created_at']}\n\n"
            "Abra pitch.html para apresentar ou imprimir em PDF. pitch.md contém a fala sugerida. "
            "validacao.md/json e rastreabilidade.csv contêm verificações técnicas locais. "
            "aceitacao.csv registra os cenários de uso e sua avaliação manual. "
            "Aprovação técnica e aceitação pelo usuário são estados distintos. "
            "O programa Informix-4GL e o banco não foram executados.\n"
        ),
        "fonte_analisado.4gl": report["source"],
        "validacao.json": json_text({"validation": report, "acceptance": acceptance}),
        "validacao.md": validation_markdown(report, acceptance),
        "rastreabilidade.csv": table_csv(report["checks"]),
        "aceitacao.csv": table_csv(acceptance),
        "pitch.md": pitch_markdown(pitch),
        "pitch.html": pitch_html(pitch),
    }
    if junit is not None:
        files["pytest.xml"] = junit
    if report.get("functional"):
        files["funcional_requisitos.csv"] = table_csv(report["functional"]["requirements"])
        files["funcional_casos.csv"] = table_csv(report["functional"]["tests"])
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content if isinstance(content, bytes) else content.encode("utf-8"))
    return output.getvalue()
