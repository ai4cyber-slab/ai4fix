import { readFileSync } from "fs";
import * as vscode from "vscode";
import { ANALYZER_MENTION, PATCH_FOLDER, PROJECT_FOLDER } from "../constants";
import { IFix, Iissue, IIssueRange } from "../interfaces";
import { getIssues } from "../services/fakeAiFixCode";
import * as logging from "../services/logging";
var path = require("path");
var upath = require("upath");

let issueGroups = {};

async function initIssues() {
  issueGroups = await getIssues();
}

export async function refreshDiagnostics(
  doc: vscode.TextDocument,
  aiFixCodeDiagnostics: vscode.DiagnosticCollection
) {
  try {
    const diagnostics: vscode.Diagnostic[] = [];
    await initIssues();

    if (issueGroups) {

      Object.values(issueGroups).forEach((issues: any) => {
        issues.forEach((issue: any) => {
          if (issue.JavaFileName === (upath.basename(doc.uri.fsPath))) {
            const diagnostic = createItemDiagnostic(doc, issue);
            diagnostics.push(diagnostic);
          }
        });
      });
    }

    aiFixCodeDiagnostics.set(doc.uri, diagnostics);
    logging.LogInfo("Finished diagnosis.");
  } catch (error) {
    console.error("Unable to run diagnosis on file:", error);
    logging.LogErrorAndShowErrorMessage(
      "Unable to run diagnosis on file: " + error,
      "Unable to run diagnosis on file: " + error
    );
  }
}

function createItemDiagnostic(
  doc: vscode.TextDocument,
  issue: any
): vscode.Diagnostic {
  const range = new vscode.Range(
    issue.textRange.startLine - 1,
    issue.textRange.startColumn,
    issue.textRange.endLine - 1,
    issue.textRange.endColumn
  );

  const message = `${issue.issueName}: ${issue.explanation}`;

  const diagnostic = new vscode.Diagnostic(
    range,
    message,
    vscode.DiagnosticSeverity.Information
  );
  diagnostic.code = ANALYZER_MENTION;

  let relatedInformation: vscode.DiagnosticRelatedInformation[] = issue.patches.map((patch: any) => {
    return new vscode.DiagnosticRelatedInformation(
      new vscode.Location(doc.uri, range),
      patch.explanation
    );
  });

  diagnostic.relatedInformation = relatedInformation;

  return diagnostic;
}

export function subscribeToDocumentChanges(
  context: vscode.ExtensionContext,
  emojiDiagnostics: vscode.DiagnosticCollection
): void { }
