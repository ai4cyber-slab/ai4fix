import { readFileSync } from 'fs';
import * as vscode from 'vscode';
import { ISSUES_PATH, PATCH_FOLDER, PROJECT_FOLDER } from '../constants';
import { IFix, Iissue, IIssueRange } from '../interfaces';
import { getIssues2 } from '../services/fakeAiFixCode';
var path = require('path');
var upath = require('upath');

let issueGroups = {};
let disposableAnalyzerProvider: vscode.Disposable;
let disposableAnalyzerInfoProvider: vscode.Disposable;

async function initIssues() {
  issueGroups = await getIssues2();
  console.log(issueGroups);
}

export function initActionCommands(context: vscode.ExtensionContext) {
  initIssues().then(() => {
    // Dispose already created providers to avoid duplication issues:
    if (disposableAnalyzerProvider) {
      disposableAnalyzerProvider.dispose();
    }

    if (disposableAnalyzerInfoProvider) {
      disposableAnalyzerInfoProvider.dispose();
    }

    // Register the providers for code actions
    context.subscriptions.push(
      disposableAnalyzerProvider = vscode.languages.registerCodeActionsProvider("*", new Analyzer(), {
        providedCodeActionKinds: Analyzer.providedCodeActionKinds
      })
    );

    context.subscriptions.push(
      disposableAnalyzerInfoProvider = vscode.languages.registerCodeActionsProvider("*", new AnalyzerInfo(), {
        providedCodeActionKinds: AnalyzerInfo.providedCodeActionKinds
      })
    );
  });
}

export class Analyzer implements vscode.CodeActionProvider {

  public static readonly providedCodeActionKinds = [
    vscode.CodeActionKind.QuickFix
  ];

  // This function is called whenever the user selects text or places the cursor in an area that contains a Diagnostic:
  public async provideCodeActions(document: vscode.TextDocument, range: vscode.Range): Promise<vscode.CodeAction[] | undefined> {

    let commandActions: vscode.CodeAction[] = [];
    issueGroups = await getIssues2();
    let hasFixes = false; // Flag to check if fixes are available
    
    if (issueGroups) {
      Object.values(issueGroups).forEach((issues: any) => {
        issues.forEach((issue: any) => {
          if (issue.textRange.startLine - 1 === range.start.line) {
            const fixRange = issues.textRange;
            const warningId = issue.id; // Capture the warning ID even if there are no patches

            issue.patches.sort((a: any, b: any) => b.score - a.score);
            
            // If there are fixes, set hasFixes to true
            if (issue.patches.length > 0) {
              hasFixes = true;
            }

            issue.patches.forEach((fix: IFix) => {
              const fixText = fix.explanation;
              const patchPath = fix.path;

              var patch = '';
              var patch_folder = PATCH_FOLDER;

              if (process.platform === 'win32') {
                if (patch_folder[0] === '/' || patch_folder[0] === '\\') {
                  patch_folder = patch_folder.substring(1);
                }
              }

              try {
                patch = readFileSync(upath.join(patch_folder, patchPath), "utf8");
              } catch (err) {
                console.log(err);
              }

              var sourceFileMatch = /--- ([^ \n\r\t]+).*/.exec(patch);
              var sourceFilePath: string;

              if (sourceFileMatch && sourceFileMatch[1]) {
                sourceFilePath = sourceFileMatch[1];
              } else {
                throw Error("Unable to find source file in '" + patch + "'");
              }

              let openedFilePath = vscode.window.activeTextEditor?.document.uri.path;

              let projectFolder = PROJECT_FOLDER;
              sourceFilePath = upath.normalize(upath.join(PROJECT_FOLDER, vscode.Uri.file(sourceFilePath).fsPath).toLowerCase());
              openedFilePath = upath.normalize(vscode.Uri.file(openedFilePath!).fsPath.toLowerCase());
              if (process.platform === 'linux' || process.platform === 'darwin') {
                if (sourceFilePath![0] !== '/')
                  sourceFilePath = '/' + sourceFilePath;
                if (openedFilePath![0] !== '/')
                  openedFilePath = '/' + openedFilePath;
              }

              let editor = vscode.window.activeTextEditor;
              let issuesPath = ISSUES_PATH;
              let cursorPosition = editor?.selection.start;

              if (cursorPosition) {
                // Ensure the cursor is on the correct line for this issue
                if (sourceFilePath === openedFilePath && cursorPosition!.line === range.start.line) {
                  // Push the patch command
                  commandActions.push(this.createCommand(fixText, fixRange, patchPath));
                }

                let currentFilePath = vscode.window.activeTextEditor?.document.uri.path!;
                if (currentFilePath) {
                  // Check if the Python script command is already added
                  let pythonCommandExists = commandActions.some(action => action.title === "AI: generate new patch");
                  if (!pythonCommandExists) {
                    // Push the Python script command
                    commandActions.push(this.createPythonCommand("AI: generate new patch", range, warningId, currentFilePath, projectFolder, patch_folder, issuesPath));
                  }
                } else {
                  console.log("No open file " + currentFilePath);
                }
              }
            });

            // Add the Python script option, even if there are no available patches
            if (!hasFixes) {
              let currentFilePath = vscode.window.activeTextEditor?.document.uri.path!;
              if (currentFilePath) {
                // Push the Python script command
                commandActions.push(this.createPythonCommand("AI: generate new patch", range, warningId, currentFilePath, PROJECT_FOLDER, PATCH_FOLDER, ISSUES_PATH));
              }
            }
          }
        });
      });
    }

    return commandActions;
  }

  private createCommand(fixText: string, fixRange: IIssueRange, patchPath: string): vscode.CodeAction {
    const action = new vscode.CodeAction(fixText, vscode.CodeActionKind.QuickFix);
    action.command = { command: 'aifix4seccode-vscode.loadPatchFile', arguments: [patchPath], title: 'Refactor code with possible fixes.', tooltip: 'This will open a diff view with the generated patch.' };
    return action;
  }

  // Create the new command for running the Python script
  private createPythonCommand(title: string, range: vscode.Range, warningId: string, javaFilePath: string, projectFolder: string, patchFolder: string, issuesPath: string): vscode.CodeAction {
    const action = new vscode.CodeAction(title, vscode.CodeActionKind.QuickFix);
    action.command = {
      command: 'aifix4seccode-vscode.generatePatchForSingleWarning',
      arguments: [warningId, javaFilePath, projectFolder, patchFolder, issuesPath],
      title: title,
      tooltip: 'This will run a Python script.'
    };
    return action;
  }
}

export class AnalyzerInfo implements vscode.CodeActionProvider {

  public static readonly providedCodeActionKinds = [
    vscode.CodeActionKind.QuickFix,
  ];

  provideCodeActions(document: vscode.TextDocument, range: vscode.Range | vscode.Selection, context: vscode.CodeActionContext, token: vscode.CancellationToken): vscode.CodeAction[] {
    // For each diagnostic entry that has the matching `code`, create a code action command
    return [];
  }
}