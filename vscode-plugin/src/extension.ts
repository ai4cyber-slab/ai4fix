import { init } from './commands';
//import { commands, ExtensionContext, languages, ProgressLocation, window, workspace, StatusBarItem, StatusBarAlignment } from 'vscode';
import * as vscode from 'vscode';
import { log } from './logger';
import { getVSCodeDownloadUrl } from 'vscode-test/out/util';
import { JsonOutlineProvider } from './providers/jsonOutline';
import { initActionCommands } from './language/codeActions';
import * as logging from './services/logging';
import * as constants from './constants';
import { refreshDiagnostics } from "./language/diagnostics";
import { exec } from 'child_process';
import { SCRIPT_PATH } from './constants';
var fs = require('fs');

var upath = require("upath");
var path = require("path");

export let analysisDiagnostics = vscode.languages.createDiagnosticCollection('aifix4seccode');

let analysisStatusBarItem: vscode.StatusBarItem;
let analyzeCurrentFileStatusBarItem: vscode.StatusBarItem;
let undoFixStatusBarItem: vscode.StatusBarItem;
let generateTestForCurrentFileStatusBarItem: vscode.StatusBarItem;

export function activate(context: vscode.ExtensionContext) {

  const jsonOutlineProvider = new JsonOutlineProvider(context);
  vscode.window.registerTreeDataProvider('aifix4seccode-vscode_jsonOutline', jsonOutlineProvider);

  init(context, jsonOutlineProvider);
  log(process.env);

  // status bar items:
  // Start analysis status bar item:
  analysisStatusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  analysisStatusBarItem.command = 'aifix4seccode-vscode.getOutputFromAnalyzer';
  context.subscriptions.push(analysisStatusBarItem);

  analysisStatusBarItem.text = "$(symbol-misc) Start Analysis";
  analysisStatusBarItem.show();

  // Analyze current file:
  analyzeCurrentFileStatusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  analyzeCurrentFileStatusBarItem.command = "aifix4seccode-vscode.getOutputFromAnalyzerPerFile";
  context.subscriptions.push(analyzeCurrentFileStatusBarItem);

  analyzeCurrentFileStatusBarItem.text = "$(symbol-keyword) Analyze Current File";
  analyzeCurrentFileStatusBarItem.show();

  // Undo last fix:
  undoFixStatusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  undoFixStatusBarItem.command = 'aifix4seccode-vscode.undoLastFix';
  context.subscriptions.push(undoFixStatusBarItem);

  undoFixStatusBarItem.text = "$(undo) Undo Last Fix";
  undoFixStatusBarItem.show();

  // Generate Test for Current File:
  generateTestForCurrentFileStatusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  generateTestForCurrentFileStatusBarItem.command = 'aifix4seccode-vscode.generateTestForCurrentFile';
  context.subscriptions.push(generateTestForCurrentFileStatusBarItem);

  generateTestForCurrentFileStatusBarItem.text = "$(beaker) Generate Test for Current File";
  generateTestForCurrentFileStatusBarItem.show();

  // On settings change restart prompt:
  vscode.workspace.onDidChangeConfiguration(event => {
    const action = 'Reload';

    // save extension settings parameters to config file:

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
  })

  // Start up log:
  logging.LogInfo("Extension started!");
  vscode.window.showInformationMessage('This extension is used for analyzing your project for issues. If you have no project folder opened please open it, or include it in the \'AIFix4SecCode\' Extension settings.'
    , 'Open Settings').then(selected => {
      vscode.commands.executeCommand('workbench.action.openSettings', 'AIFix4SecCode');
    });
  logging.ShowInfoMessage("AIFix4SecCode installed. Welcome!");

  // Handle file save with running a file analysis:
  vscode.workspace.onDidSaveTextDocument((document: vscode.TextDocument) => {
    if (document.languageId === "java" && document.uri.scheme === "file") {
      vscode.commands.executeCommand("aifix4seccode-vscode.getOutputFromAnalyzerPerFile");
      async () => {
        await refreshDiagnostics(
          vscode.window.activeTextEditor!.document,
          analysisDiagnostics
        );
        // set selection of warning:
        //await commands.setIssueSelectionInEditor(patchPath);
      }
    }
  });

vscode.commands.registerCommand('aifix4seccode-vscode.generatePatchForSingleWarning', (warningId: string, javaFilePath: string, projectFolder: string, patchFolder: string, issues_path: string) => {
  // Construct the command with arguments for the Python script
  let pythonScriptPath = SCRIPT_PATH;
  pythonScriptPath = path.join(pythonScriptPath, 'single_warning_patch.py');
  const command = `python3 ${pythonScriptPath} -j ${javaFilePath} -wid ${warningId} -pp ${projectFolder} -dod ${patchFolder} -jl ${issues_path}`;

  // Execute the Python script
  exec(command, (error, stdout, stderr) => {
    if (error) {
      vscode.window.showErrorMessage(`Error running Python script: ${stderr}`);
      return;
    }
    vscode.window.showInformationMessage(`Patch Generated with Success!: ${stdout}`);
  });
});

}