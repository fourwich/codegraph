import * as path from "path";
import * as vscode from "vscode";
import { runIndex, runWhy } from "./client";
import { renderWhyHtml } from "./webview";

function cliPath(): string {
  return vscode.workspace.getConfiguration("codegraph").get<string>("cliPath") || "codegraph";
}

function backend(): string {
  return vscode.workspace.getConfiguration("codegraph").get<string>("backend") || "sqlite";
}

export function activate(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("codegraph.showDecision", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        void vscode.window.showWarningMessage("CodeGraph: open a file first");
        return;
      }
      const doc = editor.document;
      const line = editor.selection.active.line + 1;
      const file = doc.uri.fsPath;
      const snippetStart = Math.max(0, line - 3);
      const snippetEnd = Math.min(doc.lineCount, line + 2);
      const snippet = doc.getText(
        new vscode.Range(snippetStart, 0, snippetEnd, 0)
      );
      try {
        const result = await runWhy(cliPath(), file, line, backend());
        if (!result) {
          void vscode.window.showWarningMessage("CodeGraph: no result from CLI");
          return;
        }
        const panel = vscode.window.createWebviewPanel(
          "codegraphDecision",
          "CodeGraph: Decision",
          vscode.ViewColumn.Beside,
          { enableScripts: true }
        );
        panel.webview.html = renderWhyHtml(result, snippet);
        panel.webview.onDidReceiveMessage((msg) => {
          if (msg && msg.type === "openBrowser") {
            void vscode.env.openExternal(
              vscode.Uri.parse("https://fourwich.github.io/codegraph")
            );
          }
        });
      } catch (err) {
        void vscode.window.showErrorMessage(
          `CodeGraph: ${err instanceof Error ? err.message : String(err)}`
        );
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codegraph.indexWorkspace", async () => {
      const folders = vscode.workspace.workspaceFolders;
      const root = folders?.[0]?.uri.fsPath;
      if (!root) {
        void vscode.window.showWarningMessage("CodeGraph: open a workspace folder");
        return;
      }
      try {
        const result = await runIndex(cliPath(), root, backend());
        void vscode.window.showInformationMessage(
          `CodeGraph: indexed ${result.nodes} nodes, ${result.decisions} decisions`
        );
      } catch (err) {
        void vscode.window.showErrorMessage(
          `CodeGraph index failed: ${err instanceof Error ? err.message : String(err)}`
        );
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codegraph.openWebView", () => {
      void vscode.env.openExternal(vscode.Uri.parse("http://127.0.0.1:8080/"));
    })
  );

  const autoIndex = vscode.workspace
    .getConfiguration("codegraph")
    .get<boolean>("autoIndex");
  if (autoIndex) {
    void vscode.commands.executeCommand("codegraph.indexWorkspace");
  }
}

export function deactivate(): void {
  /* no-op */
}

// keep path import referenced for future workspace path joins
void path;
