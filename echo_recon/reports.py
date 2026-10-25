"""HTML, JSON and Markdown report generation with HTML escaping."""
from __future__ import annotations

import html
import json
from pathlib import Path


def write_reports(out_dir: Path, findings: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")
    rows = []
    md_rows = ["| Tool | Status | Exit | Duration | Output |", "|---|---|---:|---:|---|"]
    for item in findings.get("tools", []):
        tool = html.escape(str(item.get("tool", "")))
        status = html.escape(str(item.get("status", "")))
        code = html.escape(str(item.get("returncode", "—")))
        duration = html.escape(str(item.get("duration_seconds", 0)))
        message = html.escape(str(item.get("message", "")))
        output = html.escape(str(item.get("output_file", "")))
        rows.append(f"<tr><td>{tool}</td><td><span class='status {status}'>{status}</span><br><small>{message}</small></td><td>{code}</td><td>{duration}s</td><td><a href='{output}'>{output or '—'}</a></td></tr>")
        md_rows.append(f"| {item.get('tool','')} | {item.get('status','')} | {item.get('returncode','—')} | {item.get('duration_seconds',0)}s | `{item.get('output_file','')}` |")
    notes = "".join(f"<li>{html.escape(str(n))}</li>" for n in findings.get("notes", []))
    safe_target = html.escape(str(findings.get("target", "")))
    safe_status = html.escape(str(findings.get("status", "unknown")))
    document = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Echo Recon Report</title>
<style>body{{background:#0b0d12;color:#e7e9ee;font:15px/1.6 system-ui,sans-serif;margin:0;padding:28px}}main{{max-width:1100px;margin:auto}}h1{{font-size:28px}}.muted,small{{color:#9aa3b2}}.panel{{background:#151923;border:1px solid #2b3140;border-radius:14px;padding:18px;margin:16px 0}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:11px;border-bottom:1px solid #2a3040;vertical-align:top}}th{{color:#a8b3c7}}a{{color:#7dc7ff}}.status{{font-weight:700}}.ok,.completed{{color:#6ee7b7}}.failed,.timeout,.missing{{color:#fda4af}}.cancelled,.partial{{color:#fcd34d}}code{{overflow-wrap:anywhere}}</style></head><body><main>
<h1>Echo Recon <span class="muted">/ report</span></h1><p class="muted">Linux Edition · {html.escape(str(findings.get('run_id','')))}</p>
<section class="panel"><b>Target</b><p><code>{safe_target}</code></p><b>Run status:</b> <span class="status {safe_status}">{safe_status}</span><p class="muted">Started: {html.escape(str(findings.get('started_at','')))}<br>Finished: {html.escape(str(findings.get('finished_at','')))}<br>Per-tool watchdog: {int(findings.get('max_runtime_seconds_per_tool',0))} seconds</p><p>In-scope hosts recorded: {int(findings.get('host_count_in_scope',0))}</p></section>
<section class="panel"><h2>Tool results</h2><table><thead><tr><th>Tool</th><th>Status / notes</th><th>Exit</th><th>Duration</th><th>Raw output</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
<section class="panel"><h2>Scope hosts</h2><ul>{''.join(f'<li><code>{html.escape(str(h))}</code></li>' for h in findings.get('hosts_in_scope',[]))}</ul></section>
<section class="panel"><h2>Interpretation and limitations</h2><ul>{notes}</ul></section></main></body></html>"""
    (out_dir / "report.html").write_text(document, encoding="utf-8")
    summary = ["# Echo Recon Report", "", f"- **Target:** `{findings.get('target','')}`", f"- **Status:** {findings.get('status','unknown')}",
               f"- **Started:** {findings.get('started_at','')}", f"- **Finished:** {findings.get('finished_at','')}", "", *md_rows, "", "## Notes"]
    summary.extend(f"- {n}" for n in findings.get("notes", []))
    (out_dir / "report.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
