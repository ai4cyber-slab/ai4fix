import { getIssues } from './services/fakeAiFixCode';
import { writeFileSync } from 'fs';
import { updateUserDecisions } from './commands';
import { utf8Stream, ANALYZER_USE_DIFF_MODE } from './constants';
import { workspace, window, ProgressLocation } from 'vscode';


let issueGroups: any;

async function initIssues() {
  issueGroups = await getIssues();
}

const pathDescription: RegExp = /((.|\n|\r)*)@@\n/g;
const eof = /\n$/;

type Line = {
  added: boolean;
  removed: boolean;
  eof: boolean;
  code: string;
};

type LineType = keyof Pick<Line, 'added' | 'removed'>;
type Side = 'left' | 'right';

const eofR = /\\ No newline at end of file/;

export function patchToCodes(patch: string) {
  const onlyCode = patch.replace(pathDescription, '').replace(eof, '');
  const patchHasEof = !patch.match(eofR);

  const lines = onlyCode.split('\n').map((line) => ({
    added: line.startsWith('+'),
    removed: line.startsWith('-'),
    code: line.substr(1, line.length),
    eof: !!line.match(eofR),
  }));

  const extractSide = (side: Side) => {
    const lineTypeToRemove: LineType = side === 'left' ? 'added' : 'removed';
    const sideHasEof = !!lines[lines.findIndex((l) => l.eof) - 1]?.[
      lineTypeToRemove
    ];

    const sideLines = lines.reduce<string[]>((acc, curr, idx) => {
      if (curr[lineTypeToRemove] || curr.eof) {
        return acc;
      }
      return [...acc, curr.code];
    }, []);
    if (patchHasEof || sideHasEof) {
      sideLines.push('');
    }

    return sideLines.join('\n');
  };

  const leftContent = extractSide('left');
  const rightContent = extractSide('right');

  return {
    leftContent,
    rightContent,
  };
}

export function applyPatchToFile(leftPath: string, rightContent: string, patchPath: string, autoApply: boolean) {
  if (leftPath) {
    if (!rightContent) {
      window.showErrorMessage('Failed to apply patch to source file! \n Make sure that your configuration is correct. Also make sure that the source file has not been patched already by this patch before! This issue may occour if the patch syntax is incorrect.');
      return;
    }

    // Overwrites the file with the patch's fixes.
    writeFileSync(leftPath, rightContent, utf8Stream);

    // let fixedContent = readFileSync(leftPath, "utf-8");
    // console.log("APPLIED PATCH CONTENT:", fixedContent);

    // Updates the issues.json so the fix will no longer show up.
    initIssues().then(() => {
      if (issueGroups) {
        Object.values(issueGroups).forEach((issues: any) => {
          issues.forEach((issue: any) => {
            if (issue.patches.some((x: any) => x.path === patchPath || patchPath.includes(x.path))) {
              delete issueGroups[issues];
            }
          });
        });
      }

      // let issuesPath = ISSUES_PATH;
      // writeFileSync(issuesPath!, issuesStr, utf8Stream);

      if (!autoApply) {
        // Opens up the file that has been patched in the editor.
        workspace.openTextDocument(leftPath).then(document => {
          window.showTextDocument(document).then(() => {
            window.withProgress({ location: ProgressLocation.Notification, title: 'Loading Diagnostics...' }, async () => {
              // Refreshes the diagnosis on the file to show the remaining suggestions.
              // await refreshDiagnostics(window.activeTextEditor!.document, analysisDiagnostics);

              // User decisions are updated here in patch mode (and at extendedWebview in diff mode):
              if (ANALYZER_USE_DIFF_MODE == "view Patch files") {
                updateUserDecisions('applied', patchPath, leftPath);
              }
            });
          });
        });
      }

    });

    //window.showInformationMessage('Content saved to path: ' + leftPath);
    return leftPath;
  }
  return '';
}
