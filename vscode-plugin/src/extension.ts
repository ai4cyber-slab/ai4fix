import { init, refreshDiagnosticsWithoutAnalysis } from './commands';
import * as vscode from 'vscode';
import { log } from './logger';
import { JsonOutlineProvider } from './providers/jsonOutline';
import * as logging from './services/logging';
import { refreshDiagnostics } from "./language/diagnostics";
import { exec } from 'child_process';
import { SCRIPT_PATH } from './constants';
import * as fs from 'fs';
import * as upath from "upath";
import * as path from "path";

export let analysisDiagnostics = vscode.languages.createDiagnosticCollection('aifix4seccode');

let analysisStatusBarItem: vscode.StatusBarItem;
let analyzeCurrentFileStatusBarItem: vscode.StatusBarItem;
let undoFixStatusBarItem: vscode.StatusBarItem;
let generateTestForCurrentFileStatusBarItem: vscode.StatusBarItem;

export async function activate(context: vscode.ExtensionContext) {

  const jsonOutlineProvider = new JsonOutlineProvider(context);
  vscode.window.registerTreeDataProvider('aifix4seccode-vscode_jsonOutline', jsonOutlineProvider);

  // Initialize the analysis status bar item
  analysisStatusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  analysisStatusBarItem.command = 'aifix4seccode-vscode.getOutputFromAnalyzer';
  analysisStatusBarItem.text = "$(symbol-misc) Start Analysis";
  analysisStatusBarItem.show();
  context.subscriptions.push(analysisStatusBarItem);

  // Initialize other status bar items similarly
  analyzeCurrentFileStatusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  analyzeCurrentFileStatusBarItem.command = "aifix4seccode-vscode.getOutputFromAnalyzerPerFile";
  analyzeCurrentFileStatusBarItem.text = "$(symbol-keyword) Scan Current File";
  analyzeCurrentFileStatusBarItem.show();
  context.subscriptions.push(analyzeCurrentFileStatusBarItem);

  undoFixStatusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  undoFixStatusBarItem.command = 'aifix4seccode-vscode.undoLastFix';
  undoFixStatusBarItem.text = "$(undo) Undo Last Fix";
  undoFixStatusBarItem.show();
  context.subscriptions.push(undoFixStatusBarItem);

  // generateTestForCurrentFileStatusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  // generateTestForCurrentFileStatusBarItem.command = 'aifix4seccode-vscode.generateTestForCurrentFile';
  // generateTestForCurrentFileStatusBarItem.text = "$(beaker) Generate Test for Current File";
  // generateTestForCurrentFileStatusBarItem.show();
  // context.subscriptions.push(generateTestForCurrentFileStatusBarItem);

  // Initialize commands with the analysisStatusBarItem
  init(context, jsonOutlineProvider, analysisStatusBarItem);

  log(process.env);

  // On settings change restart prompt:
  vscode.workspace.onDidChangeConfiguration(event => {
    const action = 'Reload';

    vscode.window
      .showInformationMessage(
        `Reload window in order for change in extension AIFix4SecCode configuration to take effect.`,
        action
      )
      .then(selectedAction => {
        if (selectedAction === action) {
          vscode.commands.executeCommand('workbench.action.reloadWindow');
        }
      });
  });

  // Start up log:
  logging.LogInfo("Extension started!");
  vscode.window.showInformationMessage(
    'This extension is used for analyzing your project for issues. If you have no project folder opened please open it, or include it in the \'AIFix4SecCode\' Extension settings.',
    'Open Settings'
  ).then(selected => {
    if (selected === 'Open Settings') {
      vscode.commands.executeCommand('workbench.action.openSettings', 'AIFix4SecCode');
    }
  });
  logging.ShowInfoMessage("AIFix4SecCode installed. Welcome!");

  await refreshDiagnosticsWithoutAnalysis(context);

  // Handle file save with running a file analysis:
  vscode.workspace.onDidSaveTextDocument((document: vscode.TextDocument) => {
    if (document.languageId === "java" && document.uri.scheme === "file") {
      vscode.commands.executeCommand("aifix4seccode-vscode.getOutputFromAnalyzerPerFile");
      // Optional: Refresh diagnostics after analysis
      (async () => {
        await refreshDiagnostics(
          vscode.window.activeTextEditor!.document,
          analysisDiagnostics
        );
      })();
    }
  });

  // Register the generatePatchForSingleWarning command directly here
  vscode.commands.registerCommand('aifix4seccode-vscode.generatePatchForSingleWarning', (warningId, javaFilePath, projectFolder, patchFolder, issues_path) => {
    // Construct the command with arguments for the Python script
    let pythonScriptPath = SCRIPT_PATH;
    pythonScriptPath = path.join(pythonScriptPath, 'single_warning_patch.py');
    const command = `python3 ${pythonScriptPath} -j "${javaFilePath}" -wid "${warningId}" -pp "${projectFolder}" -dod "${patchFolder}" -jl "${issues_path}"`;

    // Execute the Python script
    exec(command, (error, stdout, stderr) => {
      if (error) {
        vscode.window.showErrorMessage(`Error running Python script: ${stderr}`);
        return;
      }

      // Parse stdout to check if the patch was generated
      const patchGeneratedRegex = /Patch generated:\s*(.*)/;
      const match = stdout.match(patchGeneratedRegex);

      if (!match) {
        vscode.window.showErrorMessage(`Patch generation failed. Python script ran successfully but no patch was created.`);
        return;
      }

      const diffFilePath = match[1].trim();

      vscode.window.showInformationMessage(`Patch Generated with Success!`);
      // Close and reopen the current file
      const editor = vscode.window.activeTextEditor;
      if (editor) {
        const document = editor.document;
        const filePath = document.fileName;

        vscode.commands.executeCommand('workbench.action.closeActiveEditor').then(() => {
          vscode.workspace.openTextDocument(filePath).then((doc) => {
            vscode.window.showTextDocument(doc);
          });
        });
      }
      refreshDiagnosticsWithoutAnalysis(context);
    });

  });
}