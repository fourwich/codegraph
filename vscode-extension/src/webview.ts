import type { DecisionCard, WhyResult } from "./types";

function esc(s: string): string {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function card(d: DecisionCard): string {
  const alts = (d.alternatives || [])
    .map((a) => `<li>${esc(a)}</li>`)
    .join("");
  const cons = (d.constraints || [])
    .map((c) => `<li>${esc(c)}</li>`)
    .join("");
  return `
  <article class="card">
    <h3>${esc(d.content)}</h3>
    <p><strong>Reason</strong> ${esc(d.reason || "—")}</p>
    <p><strong>Source</strong> ${esc(d.source_ref || d.source)}</p>
    <p><strong>Status</strong> ${esc(d.status)} · <strong>Confidence</strong> ${(d.confidence * 100).toFixed(0)}%</p>
    ${alts ? `<p><strong>Alternatives</strong></p><ul>${alts}</ul>` : ""}
    ${cons ? `<p><strong>Constraints</strong></p><ul>${cons}</ul>` : ""}
  </article>`;
}

export function renderWhyHtml(result: WhyResult, snippet: string): string {
  const decisions = result.decisions || [];
  const body = decisions.length
    ? decisions.map(card).join("")
    : `<p class="empty">No decision record found</p>`;
  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<style>
  body { font-family: var(--vscode-font-family); color: var(--vscode-foreground); padding: 12px; }
  h2 { font-size: 14px; margin: 0 0 8px; }
  .meta { color: var(--vscode-descriptionForeground); font-size: 12px; margin-bottom: 12px; }
  pre { background: var(--vscode-editor-background); padding: 8px; border-radius: 6px; overflow: auto; }
  .card { border: 1px solid var(--vscode-panel-border); border-radius: 8px; padding: 10px; margin-bottom: 10px; }
  .empty { color: var(--vscode-descriptionForeground); }
  button { margin-top: 8px; }
</style></head><body>
  <h2>CodeGraph decision</h2>
  <div class="meta">${esc(result.file)}:${result.line}</div>
  ${result.node ? `<div class="meta">${esc(result.node.kind)} ${esc(result.node.name)} · ${esc(result.node.commit_sha || "")}</div>` : ""}
  <pre>${esc(snippet)}</pre>
  ${body}
  <button onclick="acquireVsCodeApi().postMessage({type:'openBrowser'})">Open in browser</button>
</body></html>`;
}
