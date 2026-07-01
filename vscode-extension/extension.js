const vscode = require("vscode");
const amkawa = require("./amkawa.js");

function activate(context) {
  const cmd = vscode.commands.registerCommand("aminakawa.run", async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) { vscode.window.showErrorMessage("Aminakawa: нет открытого файла"); return; }
    const doc = editor.document;
    if (!doc.fileName.endsWith(".amkawa")) {
      vscode.window.showWarningMessage("Aminakawa: это не .amkawa файл");
    }
    await doc.save();
    runFile(doc.fileName, doc.getText());
  });
  context.subscriptions.push(cmd);
}

function runFile(fileName, code) {
  // закрыть прошлый терминал Aminakawa, если был
  vscode.window.terminals.forEach((t) => { if (t.name === "Aminakawa") t.dispose(); });

  const writeEmitter = new vscode.EventEmitter();
  let closed = false;
  let lineBuffer = "";
  let resolveLine = null;

  const output = (s) => { if (!closed) writeEmitter.fire(String(s).replace(/\n/g, "\r\n")); };
  const input = (prompt) => new Promise((resolve) => { output(prompt); resolveLine = resolve; });

  const pty = {
    onDidWrite: writeEmitter.event,
    open: () => { start(); },
    close: () => { closed = true; },
    handleInput: (data) => {
      for (const ch of data) {
        if (ch === "\r" || ch === "\n") {
          writeEmitter.fire("\r\n");
          const line = lineBuffer; lineBuffer = "";
          if (resolveLine) { const r = resolveLine; resolveLine = null; r(line); }
        } else if (ch === "\x7f" || ch === "\b") {
          if (lineBuffer.length > 0) { lineBuffer = lineBuffer.slice(0, -1); writeEmitter.fire("\b \b"); }
        } else if (ch === "\x03") {
          writeEmitter.fire("^C\r\n[остановлено]\r\n");
          closed = true;
          setTimeout(() => { try { term.dispose(); } catch (e) {} }, 50);
        } else {
          lineBuffer += ch; writeEmitter.fire(ch);
        }
      }
    },
  };

  const term = vscode.window.createTerminal({ name: "Aminakawa", pty });
  term.show();

  async function start() {
    const label = fileName.split(/[\\/]/).pop();
    output("\x1b[2m▶ " + label + "\x1b[0m\n\n");
    try {
      await amkawa.run(code, { output, input });
    } catch (e) {
      output("\ninternal error: " + (e && e.message ? e.message : String(e)) + "\n");
    }
    if (!closed) output("\n\x1b[2m[программа завершена]\x1b[0m\n");
  }
}

function deactivate() {}
module.exports = { activate, deactivate };
