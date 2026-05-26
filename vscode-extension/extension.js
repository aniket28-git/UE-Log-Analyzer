// @ts-check
const vscode = require('vscode');
const path = require('path');

function activate(context) {
    function getPython() {
        return vscode.workspace.getConfiguration('ueLogAnalyzer').get('pythonPath', 'python');
    }

    function getProjectRoot() {
        const configured = vscode.workspace.getConfiguration('ueLogAnalyzer').get('projectRoot', '');
        if (configured) return configured;
        const folders = vscode.workspace.workspaceFolders;
        return folders && folders.length > 0 ? folders[0].uri.fsPath : '';
    }

    function runInTerminal(label, cmd) {
        const terminal = vscode.window.createTerminal(label);
        terminal.show();
        terminal.sendText(cmd);
    }

    function resolveFilePath(uri) {
        if (uri && uri.fsPath) return uri.fsPath;
        const editor = vscode.window.activeTextEditor;
        return editor ? editor.document.uri.fsPath : null;
    }

    const analyzeCmd = vscode.commands.registerCommand(
        'ue-log-analyzer.analyzeFile',
        (uri) => {
            const filePath = resolveFilePath(uri);
            if (!filePath) {
                vscode.window.showErrorMessage('UE Log Analyzer: No file selected.');
                return;
            }
            const python = getPython();
            const root = getProjectRoot();
            const cwd = root ? `cd "${root}" && ` : '';
            runInTerminal('UE Log Analyzer', `${cwd}${python} -m src.main analyze "${filePath}"`);
        }
    );

    const analyzeHtmlCmd = vscode.commands.registerCommand(
        'ue-log-analyzer.analyzeFileHtml',
        async (uri) => {
            const filePath = resolveFilePath(uri);
            if (!filePath) {
                vscode.window.showErrorMessage('UE Log Analyzer: No file selected.');
                return;
            }
            const outPath = filePath.replace(/\.log$/i, '_report.html');
            const python = getPython();
            const root = getProjectRoot();
            const cwd = root ? `cd "${root}" && ` : '';
            runInTerminal(
                'UE Log Analyzer (HTML)',
                `${cwd}${python} -m src.main analyze "${filePath}" --output html -o "${outPath}"`
            );
        }
    );

    const watchCmd = vscode.commands.registerCommand(
        'ue-log-analyzer.watchFile',
        (uri) => {
            const filePath = resolveFilePath(uri);
            if (!filePath) {
                vscode.window.showErrorMessage('UE Log Analyzer: No file selected.');
                return;
            }
            const python = getPython();
            const root = getProjectRoot();
            const cwd = root ? `cd "${root}" && ` : '';
            runInTerminal(
                'UE Log Analyzer (Watch)',
                `${cwd}${python} -m src.main analyze "${filePath}" --watch`
            );
        }
    );

    const diffCmd = vscode.commands.registerCommand(
        'ue-log-analyzer.diffLogs',
        async () => {
            const beforeUri = await vscode.window.showOpenDialog({
                canSelectMany: false,
                openLabel: 'Select BEFORE log',
                filters: { 'Log files': ['log'], 'All files': ['*'] },
            });
            if (!beforeUri || beforeUri.length === 0) return;

            const afterUri = await vscode.window.showOpenDialog({
                canSelectMany: false,
                openLabel: 'Select AFTER log',
                filters: { 'Log files': ['log'], 'All files': ['*'] },
            });
            if (!afterUri || afterUri.length === 0) return;

            const python = getPython();
            const root = getProjectRoot();
            const cwd = root ? `cd "${root}" && ` : '';
            runInTerminal(
                'UE Log Analyzer (Diff)',
                `${cwd}${python} -m src.main diff "${beforeUri[0].fsPath}" "${afterUri[0].fsPath}"`
            );
        }
    );

    context.subscriptions.push(analyzeCmd, analyzeHtmlCmd, watchCmd, diffCmd);
}

function deactivate() {}

module.exports = { activate, deactivate };
