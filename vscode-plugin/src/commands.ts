import * as vscode from "vscode";
import * as logging from "./services/logging";
import * as readline from 'readline';
import * as child_process from 'child_process';
import * as fakeAiFixCode from "./services/fakeAiFixCode";
import { execSync, spawn } from "child_process";
import { showDiff } from "./webview";
import { TestView } from "./providers/testView";
import { GroupedTestView } from "./providers/testViewGrouped";
import { ExtendedWebview } from "./webview/extendedWebview";
import { applyPatchToFile } from "./patch";
import { refreshDiagnostics } from "./language/diagnostics";
import { initActionCommands } from "./language/codeActions";
import { analysisDiagnostics } from "./extension";
import { parsePatch } from 'diff';
import {
  getActiveDiffPanelWebview,
  getActiveDiffPanelWebviews,
} from "./webview/store";
import {
  readFileSync,
  existsSync,
  writeFileSync,
  appendFileSync,
} from "fs";
import {
  CONFIG,
  ISSUES_PATH,
  TEST_FOLDER,
  PATCH_FOLDER,
  PROJECT_FOLDER,
  ANALYZER_USE_DIFF_MODE,
  SetProjectFolder,
  SCRIPT_PATH,
  utf8Stream,
} from "./constants";


const { applyPatchWithWhitespaceIgnore } = require('../utils/applyPatchWrapper');
const diff = require("diff");
let path = require("path");
let upath = require("upath");
let stringify = require("json-stringify");

let activeDiffPanelWebviews = getActiveDiffPanelWebviews();

export let testView: TestView;
export let groupedTestView: GroupedTestView;

let issues: any;

let issueGroups = {};

async function initIssues() {
  issues = await fakeAiFixCode.getIssues();
  if (Object.keys(issueGroups).length === 0) {
    issueGroups = await fakeAiFixCode.getIssues2();
  }
}

export async function updateUserDecisions(
  decision: string,
  patchPath: string,
  leftPath: string
) {
  // Ask user's choice for accepting / declining the fix:
  logging.LogInfo("===== Executing showPopup command. =====");

  let inputOptions: vscode.InputBoxOptions = {
    prompt: "Please specify the reason for your choice: ",
    placeHolder: "I accepted / declined / reverted this fix because ...",
  };

  return await vscode.window.showInputBox(inputOptions).then((value) => {
    let patchRoot = PATCH_FOLDER;
    if (patchRoot) {
      let date = new Date();
      let dateStr =
        date.getFullYear().toString() +
        "/" +
        (date.getMonth() + 1).toString() +
        "/" +
        date.getDate().toString() +
        " " +
        date.getHours().toString() +
        ":" +
        date.getMinutes().toString();

      appendFileSync(
        path.join(patchRoot, "user_decisions.txt"),
        `${dateStr} == ${leftPath} original File <-> ${patchPath} patch, decision: ${decision}, reason: ${value} \n`,
        utf8Stream
      );
    }
  });
}

export async function refreshDiagnosticsWithoutAnalysis(context: vscode.ExtensionContext,) {
  let issuesPath = ISSUES_PATH;
  let generatedPatchesPath = PATCH_FOLDER;
  let subjectProjectPath = PROJECT_FOLDER;
  let jsonFilePaths: string[] = [];

  try {
    const data = readFileSync(issuesPath, "utf8");
    let lines = data.split("\n");

    jsonFilePaths = lines.filter((line: string) => line.trim().endsWith(".json"));

    if (jsonFilePaths.length === 0) {
      logging.LogError("No JSON file paths found in the issuesPath file.");
      return;
    }
  } catch (err) {
    //logging.LogError("Error reading the issuesPath file: " + err);
    return;
  }

  // Show issues treeView:
  testView = new TestView(context);
  groupedTestView = new GroupedTestView(context);

  // Initialize action commands of diagnostics made after analysis:
  initActionCommands(context);

  // Await the withProgress function
  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Loading Diagnostics...",
    },
    async () => {
      await refreshDiagnostics(vscode.window.activeTextEditor!.document, analysisDiagnostics);
    }
  );

  let output = fakeAiFixCode.getIssuesSync();
  //logging.LogInfo("issues got from analyzer output: " + JSON.stringify(output));

  logging.LogInfoAndShowInformationMessage(
    "===== Finished analysis. =====",
    "Finished analysis of project!"
  );
}

export function init(
  context: vscode.ExtensionContext,
  jsonOutlineProvider: any,
  analysisStatusBarItem: vscode.StatusBarItem
) {
  let isAnalyzing = false;
  let analysisCancellationTokenSource: vscode.CancellationTokenSource | null = null;
  // Set working directory as PROJECT_FOLDER if no path was given in config:
  if (!PROJECT_FOLDER) {
    if (
      vscode.workspace.workspaceFolders! &&
      vscode.workspace.workspaceFolders!.length > 0
    ) {
      SetProjectFolder(vscode.workspace.workspaceFolders![0].uri.path);
      logging.LogInfoAndShowInformationMessage(
        "No project folder was given, setting opened workspace as project folder.",
        "No project folder was given, setting opened workspace as project folder."
      );
    } else {
      logging.LogErrorAndShowErrorMessage(
        "No workspace directory found! Open up a workspace directory or give a project path in config.",
        "No workspace directory found! Open up a workspace directory or give a project path in config."
      );
    }

    // Filter out first backslash from project path:
    let projectFolder = PROJECT_FOLDER;
    if (projectFolder!.startsWith("/"))
      projectFolder = projectFolder!.replace("/", "");

    SetProjectFolder(projectFolder!);
  }

  context.subscriptions.push(
    vscode.commands.registerCommand("aifix4seccode-vscode.blank", blank),
    vscode.commands.registerCommand(
      'aifix4seccode-vscode.patchIssuesNow',
      patchIssuesNow
    ),
    vscode.commands.registerCommand(
      'aifix4seccode-vscode.alwaysPatchIssues',
      alwaysPatchIssues
    ),
    vscode.commands.registerCommand(
      "aifix4seccode-vscode.loadPatchFile",
      loadPatch
    ),
    vscode.commands.registerCommand(
      "aifix4seccode-vscode.applyPatch",
      applyPatch
    ),
    vscode.commands.registerCommand(
      "aifix4seccode-vscode.declinePatch",
      declinePatch
    ),
    vscode.commands.registerCommand(
      "aifix4seccode-vscode.refreshDiagnostics",
      refreshAnalysisDiagnostics
    ),
    vscode.commands.registerCommand("aifix4seccode-vscode.nextDiff", nextDiff),
    vscode.commands.registerCommand("aifix4seccode-vscode.prevDiff", prevDiff),
    vscode.commands.registerCommand(
      "aifix4seccode-vscode.getOutputFromAnalyzer",
      getOutputFromAnalyzer
    ),
    vscode.commands.registerCommand(
      "aifix4seccode-vscode.generateTestForCurrentFile",
      generateTestForCurrentFile
    ),
    vscode.commands.registerCommand(
      "aifix4seccode-vscode.getOutputFromAnalyzerPerFile",
      getOutputFromAnalyzerOfAFile
    ),
    vscode.commands.registerCommand(
      "aifix4seccode-vscode.undoLastFix",
      undoLastFix
    ),
    vscode.commands.registerCommand(
      "aifix4seccode-vscode.openUpFile",
      openUpFile
    ),
    // treeview
    vscode.commands.registerCommand("aifix4seccode-vscode_jsonOutline.refresh", () =>
      jsonOutlineProvider.refresh()
    ),
    vscode.commands.registerCommand("aifix4seccode-vscode_jsonOutline.refreshNode", (offset) =>
      jsonOutlineProvider.refresh(offset)
    ),
    vscode.commands.registerCommand("aifix4seccode-vscode_jsonOutline.renameNode", (offset) =>
      jsonOutlineProvider.rename(offset)
    ),
    vscode.commands.registerCommand("aifix4seccode-vscode_extension.openJsonSelection", (range) =>
      jsonOutlineProvider.select(range)
    ),
    vscode.commands.registerCommand(
      'aifix4seccode-vscode.cancelAnalysis',
      cancelAnalysis
    ),
  );

  vscode.commands.executeCommand("setContext", "patchApplyEnabled", false);

  function blank() {
    showDiff({ leftContent: "", rightContent: "", rightPath: "", context });
    vscode.commands.executeCommand("setContext", "patchApplyEnabled", true);
  }

  async function patchIssuesNow(item: { key: string }) {
    vscode.window.showInformationMessage(`Patching issues for ${item.key}...`);
    try {
      const issues = await fakeAiFixCode.getIssues2();
      const issueType = issues[item.key];
      if (!issueType) {
        vscode.window.showWarningMessage(`No issues found for ${item.key}.`);
        return;
      }

      for (const issueIndex in issueType) {
        const issue = issueType[issueIndex];
        for (const patchIndex in issue.patches) {
          const patch = issue.patches[patchIndex];
          // Using method from manual patch application
          viewPatchFilesMode(patch.path);
          console.log(`Applied patch: ${patch.path}`);
        }
      }

      vscode.window.showInformationMessage(`All patches applied for ${item.key}.`);
    } catch (error) {
      vscode.window.showErrorMessage(`Error patching issues for ${item.key}: ${error}`);
    }
  }

  async function alwaysPatchIssues(item: { key: string }) {
    vscode.window.showInformationMessage(`Setting always patching for ${item.key}...`);
    try {
      // TODO
      console.log("ALWAYS PATCHING:", item, item.key);
      vscode.window.showInformationMessage(`Issues patched for ${item.key}.`);
    } catch (error) {
      vscode.window.showErrorMessage(`Error patching issues for ${item.key}: ${error}`);
    }
  }

  async function refreshAnalysisDiagnostics() {
    logging.LogInfo(
      "===== Executing refreshAnalysisDiagnostics command. ====="
    );
    vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Analyzing Project...",
      },
      async () => {
        await refreshDiagnostics(
          vscode.window.activeTextEditor!.document,
          analysisDiagnostics
        );
      }
    );
  }

  async function getOutputFromAnalyzer() {
    if (isAnalyzing) {
      vscode.window.showWarningMessage('Analysis is already running.');
      return;
    }

    isAnalyzing = true;
    analysisCancellationTokenSource = new vscode.CancellationTokenSource();

    analysisStatusBarItem.text = '$(sync~spin) Analyzing...';
    analysisStatusBarItem.command = undefined; // Remove the cancel command

    logging.LogInfo('===== Analysis started from command. =====');

    try {
      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: 'Analyzing project...',
          cancellable: true,
        },
        async (progress, cancellationToken) => {
          await runOrchestratorScript(progress, cancellationToken);
        }
      );
    } catch (error) {
      logging.LogError(`Error during analysis: ${error}`);
    } finally {
      isAnalyzing = false;
      analysisCancellationTokenSource = null;
      analysisStatusBarItem.text = '$(symbol-misc) Start Analysis';
      analysisStatusBarItem.command = 'aifix4seccode-vscode.getOutputFromAnalyzer';
    }
  }

  // Implement cancelAnalysis
  function cancelAnalysis() {
    if (analysisCancellationTokenSource) {
      analysisCancellationTokenSource.cancel();
      logging.LogInfo('Analysis cancellation requested by user.');
    }
  }

  async function getDiagnosticsAfterPatch() {
    logging.LogInfo("===== Analysis started from command. =====");

    vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Analyzing project!",
        cancellable: false,
      },
      async () => {
        return refreshDiagnosticsWithoutAnalysis();
      }
    );
  }

  async function refreshDiagnosticsWithoutAnalysis() {
    let issuesPath = ISSUES_PATH;
    let jsonFilePaths: string[] = [];

    try {
      const data = readFileSync(issuesPath, "utf8");
      let lines = data.split("\n");

      jsonFilePaths = lines.filter((line: string) => line.trim().endsWith(".json"));

      if (jsonFilePaths.length === 0) {
        logging.LogError("No JSON file paths found in the issuesPath file.");
        return;
      }
    } catch (err) {
      //logging.LogError("Error reading the issuesPath file: " + err);
      return;
    }

    // Show issues treeView:
    testView = new TestView(context);
    groupedTestView = new GroupedTestView(context);

    // Initialize action commands of diagnostics made after analysis:
    initActionCommands(context);

    // Await the withProgress function
    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Loading Diagnostics...",
      },
      async () => {
        await refreshDiagnostics(vscode.window.activeTextEditor!.document, analysisDiagnostics);
      }
    );

    let output = fakeAiFixCode.getIssuesSync();
    //logging.LogInfo("issues got from analyzer output: " + JSON.stringify(output));

    logging.LogInfoAndShowInformationMessage(
      "===== Finished analysis. =====",
      "Finished analysis of project!"
    );
  }

  async function highlightIssueInEditor(textRange: any) {
    const editor = vscode.window.activeTextEditor;
    if (editor) {
      const newSelection = new vscode.Selection(
        textRange["startLine"] - 1,
        textRange["startColumn"],
        textRange["endLine"] - 1,
        textRange["endColumn"]
      );
      editor.selection = newSelection;
      editor.revealRange(
        newSelection,
        vscode.TextEditorRevealType.InCenter
      );
    }
  }

  async function runOrchestratorScript(
    progress: vscode.Progress<{ message?: string; increment?: number }>,
    cancellationToken: vscode.CancellationToken
  ) {
    const issuesPath = ISSUES_PATH;

    // Step 1: Clear the issuesPath file
    // Step 2: Define the path to orchestrator.py
    // Step 3: Spawn the orchestrator.py process
    // Step 4: Read the issuesPath file
    // Step 5: Initialize action commands related to diagnostics
    // Step 6: Refresh diagnostics with a progress indicator
    // Step 7: Get issues from the analyzer
    // Step 8: Show finished analysis message

    // 1.
    try {
      writeFileSync(issuesPath, '', 'utf8');
      logging.LogInfo(`Cleared content of the file at ${issuesPath}`);
    } catch (error) {
      logging.LogInfoAndShowInformationMessage(
        `Couldn't clear ${issuesPath}:`,
        error as any
      );
    }

    // 2.
    const scriptPath = upath.normalize(upath.join(SCRIPT_PATH, 'orchestrator.py'));

    const pythonCommand = process.platform === 'win32' ? 'python' : 'python3';

    const args = [scriptPath];

    const options: child_process.SpawnOptions = {
      cwd: PROJECT_FOLDER,
      shell: false,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
      },
    };

    logging.LogInfo(`Running orchestrator in: ${PROJECT_FOLDER}`);

    // 3.
    const childProc = spawn(pythonCommand, args, options);

    // Handle cancellation
    cancellationToken.onCancellationRequested(() => {
      logging.LogInfo('Cancellation requested. Terminating orchestrator.py...');
      if (process.platform === 'win32') {
        const pid = childProc.pid;
        const exec = require('child_process').exec;
        exec(`taskkill /PID ${pid} /T /F`, (error: any, stdout: any, stderr: any) => {
          if (error) {
            logging.LogError(`Error killing process: ${error.message}`);
          } else {
            logging.LogInfo('Process terminated successfully.');
          }
        });
      } else {
        childProc.kill('SIGINT');
      }
    });

    // Listen for lines from stdout
    const rl = readline.createInterface({
      input: childProc.stdout,
      crlfDelay: Infinity,
    });

    let totalTasks = 0;
    let completedTasks = 0;
    let workflowCompleted = false; // Flag to track if workflow is completed
    rl.on('line', (line: string) => {
      logging.LogInfo(`orchestrator.py: ${line}`);

      if (workflowCompleted) {
        return; // Stop processing further lines after workflow completion
      }

      // Remove ANSI escape sequences
      const strippedLine = line.replace(
        /\u001b\[[0-9;]*m/g,
        ''
      );
      const progressMatch = strippedLine.match(/^PROGRESS UPDATE:\s*(\d+)\/(\d+)/);
      if (progressMatch) {
        completedTasks = parseInt(progressMatch[1], 10);
        totalTasks = parseInt(progressMatch[2], 10);

        if (totalTasks > 0) {
          const increment = (1 / totalTasks) * 100;
          progress.report({
            message: `Processing issue ${completedTasks}/${totalTasks}`,
            increment: increment,
          });
        }
      }

      if (strippedLine.toLowerCase().includes('workflow execution completed')) {
        logging.LogInfo('Workflow execution completed detected.');
        workflowCompleted = true;
        progress.report({ increment: 100 });
      }
    });


    childProc.stderr.on('data', (data: Buffer) => {
      const message = data.toString();
      logging.LogInfo(`orchestrator.py : ${message}`);

      if (workflowCompleted) {
        return; // Stop processing further lines after workflow completion
      }

      if (message.toLowerCase().includes('workflow execution completed')) {
        logging.LogInfo('Workflow execution completed detected in stderr.');
        workflowCompleted = true;
        progress.report({ increment: 100 });
      }
    });

    // Handle process exit
    const processExitPromise = new Promise<void>((resolve, reject) => {
      childProc.on('close', (code, signal) => {
        if (cancellationToken.isCancellationRequested) {
          logging.LogInfo('Process was cancelled by the user.');
          resolve();
        } else if (code === 0) {
          logging.LogInfo(`orchestrator.py completed successfully with exit code ${code}`);
          resolve();
        } else {
          const error = new Error(`orchestrator.py exited with code ${code}`);
          logging.LogError(error.message);
          vscode.window.showErrorMessage(`Analysis failed: ${error.message}`);
          progress.report({ increment: 100 });
          reject(error);
        }
      });

      childProc.on('error', (error) => {
        logging.LogError(`Failed to start orchestrator.py: ${error.message}`);
        vscode.window.showErrorMessage(`Failed to start analysis: ${error.message}`);
        progress.report({ increment: 100 });
        reject(error);
      });
    });

    try {
      // Await the process to complete or be cancelled
      await processExitPromise;

      if (cancellationToken.isCancellationRequested) {
        logging.LogInfo('Analysis was cancelled by the user.');
        getDiagnosticsAfterPatch();
        return;
      }

      // Proceed with post-analysis steps if not cancelled
      // 4.
      let jsonFilePaths: string[] = [];
      try {
        const data = readFileSync(issuesPath, 'utf8');
        const lines = data.split('\n');
        jsonFilePaths = lines.filter((line: string) => line.trim().endsWith('.json'));

        if (jsonFilePaths.length === 0) {
          logging.LogInfo('No JSON file paths found in the issuesPath file.');
        }
      } catch (err) {
        logging.LogError(`Error reading the issuesPath file: ${err}`);
      }

      // 5.
      initActionCommands(context);

      // 6.
      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: 'Loading Diagnostics...',
        },
        async () => {
          await refreshDiagnosticsWithoutAnalysis();
        }
      );

      // 7.
      const output = fakeAiFixCode.getIssuesSync();
      //logging.LogInfo(`Issues got from analyzer output: ${JSON.stringify(output)}`);

      // 8.
      logging.LogInfoAndShowInformationMessage(
        '===== Finished analysis. =====',
        'Finished analysis of project!'
      );
    } catch (error) {
      logging.LogError(`Error during analysis: ${error}`);
      progress.report({ increment: 100 }); // Complete the progress bar
      throw error;
    }
  }


  async function getOutputFromAnalyzerOfAFile(JavaFilePath: any) {
    logging.LogInfo("===== Analysis of a file started from command. =====");
    if (isAnalyzing) {
      vscode.window.showWarningMessage('Analysis is already running.');
      return;
    }

    if (!JavaFilePath) {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        logging.LogError(
          'No Java file path provided, and no active text editor found. Cannot analyze.'
        );
        return;
      }
      // Use the path of the active document
      JavaFilePath = editor.document.uri.fsPath;
      logging.LogInfo(`Analyzing currently opened file: ${JavaFilePath}`);
    }
  

    isAnalyzing = true;
    analysisCancellationTokenSource = new vscode.CancellationTokenSource();

    analysisStatusBarItem.text = '$(sync~spin) Analyzing file...';
    analysisStatusBarItem.command = undefined; // Remove the cancel command

    logging.LogInfo('===== Analysis started from command. =====');

    try {
      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: 'Analyzing file...',
          cancellable: true,
        },
        async (progress, cancellationToken) => {
          await runOrchestratorOnAFile(JavaFilePath, progress, cancellationToken);
        }
      );
    } catch (error) {
      logging.LogError(`Error during analysis: ${error}`);
    } finally {
      isAnalyzing = false;
      analysisCancellationTokenSource = null;
      analysisStatusBarItem.text = '$(symbol-misc) Start Analysis';
      analysisStatusBarItem.command = 'aifix4seccode-vscode.getOutputFromAnalyzer';
    }
  }

  async function undoLastFix() {
    logging.LogInfo("===== Undo Last Fix started from command. =====");

    // Retrieve the last file path
    let lastFilePath = context.workspaceState.get<string>("lastFilePath")!;

    // Correct the file path for Windows systems
    if (process.platform === "win32") {
      const driveLetterMatch = lastFilePath.match(/^([/\\])?([a-zA-Z]):[/\\]/);
      if (driveLetterMatch) {
        const driveLetter = driveLetterMatch[2].toUpperCase();
        lastFilePath = lastFilePath.replace(/^([/\\])?[a-zA-Z]:[/\\]/, `${driveLetter}:\\`);
      }
    }

    // Normalize the path after the correction
    lastFilePath = path.normalize(lastFilePath);

    // Get the file content to revert
    const lastFileContent = context.workspaceState.get<string>("lastFileContent")!;
    const lastIssuesPath = path.normalize(context.workspaceState.get<string>("lastIssuesPath")!);
    const lastIssuesContent = JSON.parse(context.workspaceState.get<string>("lastIssuesContent")!);

    writeFileSync(lastIssuesPath, lastIssuesContent);

    writeFileSync(lastFilePath, lastFileContent);

    vscode.workspace.openTextDocument(lastFilePath).then((document) => {
      vscode.window.showTextDocument(document).then(() => {
        if (ANALYZER_USE_DIFF_MODE == "view Diffs") {
          let webview = getActiveDiffPanelWebview();
          if ("patchPath" in webview.params) {
            const appliedPatchFilePath = path.normalize(webview.params.patchPath!);

            // Reverse the header updates for all other diffs in the JSON
            revertDiffHeaders(lastFilePath, appliedPatchFilePath);

            // Update user decisions of the revert fix:
            updateUserDecisions(
              "Undo was requested by user.",
              appliedPatchFilePath,
              lastFilePath
            ).then(async () => {
              // Refresh diagnostics after undo
              getDiagnosticsAfterPatch();
            });
          }
        } else if (ANALYZER_USE_DIFF_MODE == "view Patch files") {
          let patchFilepath = path.normalize(
            JSON.parse(context.workspaceState.get<string>("openedPatchPath")!)
          );
          // Update user decisions of the revert fix:
          updateUserDecisions(
            "Undo was requested by user.",
            patchFilepath,
            lastFilePath
          ).then(async () => {
            //getOutputFromAnalyzerOfAFile();
            await refreshDiagnosticsWithoutAnalysis();
          });
        }
      });
    });

    logging.LogInfo("===== Undo Last Fix command finished executing. =====");
  }

  function revertDiffHeaders(sourceFilePath: string, appliedPatchFilePath: string) {
    const issuesJsonPaths = getIssuesJsonPathsForSourceFile(sourceFilePath);

    issuesJsonPaths.forEach(jsonPath => {
      const jsonContent = readFileSync(jsonPath, 'utf8');
      const issues = JSON.parse(jsonContent);

      const appliedPatchContent = readFileSync(appliedPatchFilePath, 'utf8');

      const appliedParsedPatch = diff.parsePatch(appliedPatchContent);
      const appliedLineShifts = computeLineShifts(appliedParsedPatch);

      issues.forEach((issue: any) => {
        issue.items.forEach((item: any) => {
          item.patches.forEach((patch: any) => {
            const patchFilePath = patch.path;

            // Skip the patch that was just undone
            if (patch.path === appliedPatchFilePath) {
              return;
            }

            // For all other patches, apply the line shifts from the applied patch
            const patchContent = readFileSync(patchFilePath, 'utf8');
            const parsedPatch = diff.parsePatch(patchContent);

            revertDiffHeader(patchFilePath, appliedLineShifts);
          });
        });
      });

      writeFileSync(jsonPath, JSON.stringify(issues, null, 2), 'utf8');
    });
  }

  function revertDiffHeader(patchFilePath: string, lineShifts: { [lineNumber: number]: number }) {
    let patchContent = readFileSync(patchFilePath, 'utf8');
    const parsedPatch = diff.parsePatch(patchContent);

    let revertedPatch = "";

    parsedPatch.forEach((hunk: { hunks: { oldStart: any; newStart: any; oldLines: any; newLines: any; lines: string[]; }[]; }) => {
      const sourceLines = patchContent.split('\n').slice(0, 2);
      revertedPatch += sourceLines.join('\n') + "\n";

      // Iterate through each hunk and revert its header
      hunk.hunks.forEach((chunk: { oldStart: any; newStart: any; oldLines: any; newLines: any; lines: string[]; }) => {
        const oldStartLine = chunk.oldStart;
        const newStartLine = chunk.newStart;

        let adjustedOldStart = oldStartLine;
        let adjustedNewStart = newStartLine;

        // Apply reverse shifts (based on the applied patch)
        for (const line in lineShifts) {
          const lineNumber = parseInt(line, 10);
          if (oldStartLine >= lineNumber) {
            adjustedOldStart -= lineShifts[lineNumber];
          }
          if (newStartLine >= lineNumber) {
            adjustedNewStart -= lineShifts[lineNumber];
          }
        }

        // Replace the header in the patch content with reverted line numbers
        const header = `@@ -${adjustedOldStart},${chunk.oldLines} +${adjustedNewStart},${chunk.newLines} @@`;

        revertedPatch += header + "\n";
        chunk.lines.forEach((line: string) => {
          revertedPatch += line + "\n";
        });
      });
    });

    writeFileSync(patchFilePath, revertedPatch, 'utf8');
  }

  async function generateTestForCurrentFile() {
    logging.LogInfo("===== Generating test for current file. =====");
    const activeEditor = vscode.window.activeTextEditor;
    if (!activeEditor) {
      vscode.window.showInformationMessage("No file is currently open.");
      return;
    }

    const currentFilePath = activeEditor.document.uri.fsPath;
    return generateTestForFile(currentFilePath);
  }

  const fs = require('fs').promises;
  async function generateTestForFile(filePath: string) {
    try {
      let pythonScriptPath = SCRIPT_PATH;
      const testFolderPath = TEST_FOLDER;
      let generatedPatchesPath = PATCH_FOLDER;
      pythonScriptPath = path.join(pythonScriptPath, 'GPTTest.py');
      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: "Generating test...",
          cancellable: false,
        },
        async () => {
          const generatedTestFilePath = await generateAndSaveTest(filePath, pythonScriptPath, testFolderPath, generatedPatchesPath);
          vscode.window.showInformationMessage(`Test and log files created: ${generatedTestFilePath}`);
          logging.LogInfo("Test generated successfully.");
          runGeneratedTest(filePath);
        }
      );
    } catch (error) {
      vscode.window.showErrorMessage("Error in test generation: " + error);
      logging.LogError("Error in test generation");
    }
  }

  async function generateAndSaveTest(filePath: string, pythonScriptPath: string, testFolderPath: string, generatedPatchesPath: string): Promise<string> {
    // const fileExtension = path.extname(filePath);
    const fileExtension = ".log"
    const baseFileName = path.basename(filePath, fileExtension);
    const generatedTestFileName = `${baseFileName}Test${fileExtension}`;
    const generatedTestFilePath = path.join(testFolderPath, generatedTestFileName);
    const diffFilePath = await findRelevantDiffFile(`${baseFileName}${fileExtension}`, generatedPatchesPath);

    const testCode: string = await runPythonScript(pythonScriptPath, filePath, path.join(testFolderPath, `${baseFileName}Test${fileExtension}`), diffFilePath) as string;
    const filteredTestCode = extractTestCode(testCode);

    await fs.writeFile(generatedTestFilePath, filteredTestCode);
    return generatedTestFilePath;
  }

  function extractTestCode(testCode: string): string {
    if (!testCode.includes('```')) {
      return testCode;
    }

    const codeBlockStart = testCode.includes('```java') ? '```java' : '```';
    const startIndex = testCode.indexOf(codeBlockStart);
    const endIndex = testCode.indexOf('```', startIndex + codeBlockStart.length);

    if (startIndex === -1 || endIndex === -1) {
      logging.LogError('Generated test may be empty.');
      return '';
    }

    return testCode.substring(startIndex + codeBlockStart.length, endIndex).trim();
  }

  let retryCount = 0;
  async function runGeneratedTest(filePath: string) {
    let subjectProjectPath = PROJECT_FOLDER;
    if (!subjectProjectPath) {
      vscode.window.showErrorMessage("Test folder path is not set in the extension settings.");
      return;
    }

    vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Running test...",
        cancellable: false,
      },
      async () => {
        const testClassName = path.basename(filePath, '.java') + 'Test';
        const testPath = path.join(subjectProjectPath);

        if (retryCount < 3) {
          try {
            await runMavenTest(testPath, testClassName);
            logging.LogInfo("Test run successfully.");
            vscode.window.showInformationMessage("Test run successfully.");
          } catch (error) {
            logging.LogError('Error running the test. Retrying...');
            retryCount++;
            generateTestForCurrentFile();
          }
        }

        if (retryCount === 3) {
          logging.LogError("Test failed after 3 attempts.");
          vscode.window.showErrorMessage("Test failed after 3 attempts.");
        }
      }
    );
  }

  const cp = require('child_process');
  const fs2 = require('fs');

  async function findRelevantDiffFile(baseFileName: any, generatedPatchesPath: string | undefined) {
    const files = await fs2.promises.readdir(generatedPatchesPath);
    for (const file of files) {
      const filePath = path.join(generatedPatchesPath, file);
      const content = await fs2.promises.readFile(filePath, 'utf8');
      if (isRelevantDiff(content, baseFileName)) {
        return filePath;
      }
    }
    return null;
  }

  function isRelevantDiff(diffContent: string, baseFileName: string) {
    const regex = /--- a\/.+\/([^\/]+)\n\+\+\+ b\/.+\/([^\/]+)/g;
    let match;
    while ((match = regex.exec(diffContent)) !== null) {
      const [, oldFileName, newFileName] = match;
      if (baseFileName === oldFileName || baseFileName === newFileName) {
        return true;
      }
    }
    return false;
  }

  function runPythonScript(scriptPath: string, filePath: string, testFilePath: string, diffFilePath: string) {
    return new Promise((resolve, reject) => {
      const command = `python "${scriptPath}" "${filePath}" "${testFilePath}" "${diffFilePath}"`;
      cp.exec(command, (error: any, stdout: string, stderr: any) => {
        if (error) {
          logging.LogErrorAndShowErrorMessage("Error during running the python script:", stderr);
          reject(error);
        } else {
          resolve(stdout);
        }
      });
    });
  }

  async function runMavenTest(pomPath: string, testClassName: string) {
    logging.LogInfo("===== Running generated test for current file. =====");
    return new Promise((resolve, reject) => {
      cp.exec(`mvn -f "${pomPath}" test -Dtest=${testClassName}`, (error: any, stdout: any, stderr: any) => {
        if (error) {
          reject(error);
        } else {
          resolve(stdout);
        }
      });
    });
  }

  function startAnalyzingFileSync() {
    return new Promise<void>((resolve) => {
      let currentFilePath = upath.normalize(
        vscode.window.activeTextEditor!.document.uri.path
      );

      let issuesPath = ISSUES_PATH;

      if (process.platform === "win32" && currentFilePath.startsWith("/")) {
        currentFilePath = currentFilePath.substring(1);
      }
      let jsonFilePath;

      try {
        const data = readFileSync(issuesPath as any, "utf8");
        let lines = data.split("\n");
        let currentFileName = path.basename(currentFilePath);
        jsonFilePath = lines.find((line: any) => path.basename(line) === currentFileName + '.json');

        if (!jsonFilePath) {
          logging.LogError("Relevant JSON file path not found for the current file.");
          return;
        }
      } catch (err) {
        logging.LogError("Error reading the issuesPath file");
        return;
      }

      logging.LogInfo("Analyzer executable finished.");
      // Get Output from analyzer:
      let output = fakeAiFixCode.getIssuesSync(currentFilePath);
      //logging.LogInfo("issues got from analyzer output: " + JSON.stringify(output));

      // Show issues treeView:
      // tslint:disable-next-line: no-unused-expression
      testView = new TestView(context);
      groupedTestView = new GroupedTestView(context);

      // Initialize action commands of diagnostics made after analysis:
      initActionCommands(context);

      vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: "Loading Diagnostics...",
        },
        async () => {
          await refreshDiagnostics(
            vscode.window.activeTextEditor!.document,
            analysisDiagnostics
          );
        }
      );

      resolve();
      logging.LogInfoAndShowInformationMessage(
        "===== Finished analysis. =====",
        "Finished analysis of project!"
      );
      //process.exit();
    });
  }

  async function openUpFile(patchPathOrIssue: string | any) {
    logging.LogInfo("===== Executing openUpFile command. =====");

    let project_folder = PROJECT_FOLDER;
    let patch_folder = PATCH_FOLDER;
    if (!PROJECT_FOLDER) {
      SetProjectFolder(vscode.workspace.workspaceFolders![0].uri.path);
    }

    let sourceFile: string;
    let textRange: any;
    try {
      if (typeof patchPathOrIssue === 'string') {
        // Existing logic for when patchPath is provided
        const patchPath = patchPathOrIssue;
        let patch = "";
        try {
          patch = readFileSync(patchPath, "utf8");
        } catch (err) {
          logging.LogErrorAndShowErrorMessage(
            String(err),
            "Unable to read in patch file: " + err
          );
        }

        const sourceFileMatch = /--- ([^ \n\r\t]+).*/.exec(patch);
        if (sourceFileMatch && sourceFileMatch[1]) {
          sourceFile = sourceFileMatch[1];
        } else {
          logging.LogErrorAndShowErrorMessage(
            "Unable to find source file in '" + patchPath + "'",
            "Unable to find source file in '" + patchPath + "'"
          );
          throw Error("Unable to find source file in '" + patchPath + "'");
        }

        // Fetch textRange using setIssueSelectionInEditor
        await setIssueSelectionInEditor(patchPath);
      } else {
        // New logic for when issue data is provided directly
        const issueData = patchPathOrIssue;
        sourceFile = issueData.sourceFile;
        textRange = issueData.textRange;
      }

      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: "Loading and opening file...",
          cancellable: false,
        },
        async (progress) => {

          // Find the full path to the source file
          const sourceFilePath = await findFileInProject(sourceFile);
          progress.report({ message: `path: '${sourceFilePath}'.` });

          if (!sourceFilePath) {
            const errorMessage = `Source file '${sourceFile}' not found in project.`;
            logging.LogErrorAndShowErrorMessage(errorMessage, errorMessage);
            throw new Error(errorMessage);
          }

          const openFilePath = vscode.Uri.file(sourceFilePath);
          logging.LogInfo(`Matched source file path: ${openFilePath.fsPath}`);

          const document = await vscode.workspace.openTextDocument(openFilePath);
          await vscode.window.showTextDocument(document);
          await setIssueSelectionInEditor(patchPathOrIssue);
          await getDiagnosticsAfterPatch();
        }
      );
    } catch (error) {
      // Display the error using a progress notification as well.
      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: "Error during file operation",
          cancellable: false,
        },
        async (progress) => {
          progress.report({ message: `Error: ${error}` });
          logging.LogErrorAndShowErrorMessage(
            `Unexpected error in openUpFile: ${error}`,
            "An unexpected error occurred while trying to open the file."
          );
        }
      );
    }

    logging.LogInfo("===== Finished openUpFile command. =====");
  }


  async function findFileInProject(fileName: string): Promise<string | null> {
    const projectFolder = PROJECT_FOLDER;

    if (!projectFolder) {
      logging.LogErrorAndShowErrorMessage(
        'Project folder is not set.',
        'Project folder is not set.'
      );
      return null;
    }

    const searchPattern = new vscode.RelativePattern(projectFolder, `**/${fileName}`);
    const excludePattern = new vscode.RelativePattern(projectFolder, '**/node_modules/**');

    const files = await vscode.workspace.findFiles(searchPattern, excludePattern);

    if (files.length > 0) {
      return files[0].fsPath;
    } else {
      return null;
    }
  }

  async function setIssueSelectionInEditor(patchPathOrIssue: string | any) {
    await initIssues();

    let targetTextRange: any = {};

    if (typeof patchPathOrIssue === 'string') {
      const patchPath = patchPathOrIssue;
      Object.values(issueGroups).forEach((issueArrays: any) => {
        issueArrays.forEach((issueArray: any) => {
          if (issueArray["patches"].some((x: any) => x["path"] === patchPath)) {
            targetTextRange = issueArray["textRange"];
          }
        });
      });
    } else {
      const issueData = patchPathOrIssue;
      targetTextRange = issueData.textRange;
    }

    await highlightIssueInEditor(targetTextRange);
  }

  async function extractLineFromPatch(patchPath: string) {
    const patchContent = await fs2.promises.readFile(patchPath, 'utf8');
    const match = /@@ -(\d+),\d+ \+\d+,\d+ @@/.exec(patchContent);

    if (match && match[1]) {
      return parseInt(match[1]);
    } else {
      throw new Error("Unable to extract line number from patch file.");
    }
  }

  function loadPatch(patchPath: string) {
    logging.LogInfo("===== Executing loadPatch command. =====");

    // ==== LOAD PATCH IN "view Patch files" MODE: ====
    if (ANALYZER_USE_DIFF_MODE == "view Diffs") {
      if (!PROJECT_FOLDER) {
        SetProjectFolder(vscode.workspace.workspaceFolders![0].uri.path);
      }

      let patch = "";
      try {
        patch = readFileSync(patchPath, "utf8");
      } catch (err) {
        logging.LogErrorAndShowErrorMessage(
          String(err),
          "Unable to read patch file: " + err
        );
      }

      let sourceFileMatch = /--- ([^ \n\r\t]+).*/.exec(patch);
      let sourceFile: string;
      if (sourceFileMatch && sourceFileMatch[1]) {
        sourceFile = sourceFileMatch[1];
      } else {
        logging.LogErrorAndShowErrorMessage(
          "Unable to find source file in '" + patchPath + "'",
          "Unable to find source file in '" + patchPath + "'"
        );
        throw Error("Unable to find source file in '" + patchPath + "'");
      }
      let destinationFileMatch = /\+\+\+ ([^ \n\r\t]+).*/.exec(patch);
      let destinationFile;
      if (destinationFileMatch && destinationFileMatch[1]) {
        destinationFile = destinationFileMatch[1];
      } else {
        logging.LogErrorAndShowErrorMessage(
          "Unable to find destination file in '" + patchPath + "'",
          "Unable to find destination file in '" + patchPath + "'"
        );
        throw Error("Unable to find destination file in '" + patchPath + "'");
      }
      let projectFolder = PROJECT_FOLDER;

      sourceFile = upath.normalize(upath.join(PROJECT_FOLDER, sourceFile));
      if (process.platform === "linux" || process.platform === "darwin") {
        if (sourceFile[0] !== "/") {
          sourceFile = "/" + sourceFile;
        }
      }

      let original = readFileSync(sourceFile, "utf8");
      let patched = applyPatchWithWhitespaceIgnore(original, patch);

      if (!patched) {
        vscode.window.showErrorMessage(
          "Failed to load patched version of this source file into a diff view! \n Make sure that your configuration is correct. Also make sure that the source file has not been patched already by this patch before! This issue may occour if the patch syntax is incorrect."
        );
        return;
      }

      if (isPatchAlreadyOpened(sourceFile)) {
        let requiredWebview = activeDiffPanelWebviews.find((webview) => {
          if ("leftPath" in webview.params) {
            if (webview.params.leftPath! === sourceFile) {
              return webview;
            }
          }
        });

        if (requiredWebview) {
          requiredWebview!.webViewPanel.reveal(vscode.ViewColumn.One, false);
        }
        return;
      }

      if (patched === false) {
        logging.LogErrorAndShowErrorMessage(
          "Failed to apply patch '" + patchPath + "' to '" + sourceFile + "'",
          "Failed to apply patch '" + patchPath + "' to '" + sourceFile + "'"
        );
        throw Error(
          "Failed to apply patch '" + patchPath + "' to '" + sourceFile + "'"
        );
      } else if (sourceFile !== destinationFile) {
        logging.LogInfo(
          "Applied '" +
          patchPath +
          "' to '" +
          sourceFile +
          "' and stored it as '" +
          destinationFile +
          "'"
        );
      } else {
        logging.LogInfo("Applied '" + patchPath + "' to '" + sourceFile + "'");
      }

      logging.LogInfo("Opening Diff view.");
      showDiff({
        patchPath: patchPath,
        leftContent: original,
        rightContent: patched,
        leftPath: sourceFile,
        rightPath: "",
        context,
        theme: vscode.window.activeColorTheme.kind.toString(),
      });
      vscode.commands.executeCommand("setContext", "patchApplyEnabled", true);
      // ==== LOAD PATCH IN "view Patch files" MODE: ====
    } else if (ANALYZER_USE_DIFF_MODE == "view Patch files") {
      vscode.workspace
        .openTextDocument(PATCH_FOLDER)
        .then((document) => {
          context.workspaceState.update(
            "openedPatchPath",
            JSON.stringify(patchPath)
          );
          vscode.window.showTextDocument(document);
        });

      vscode.commands.executeCommand("setContext", "patchApplyEnabled", true);
    }
    logging.LogInfo("===== Finished loadPatch command. =====");
  }

  function getPatchedContent(original: string, params: any) {
    if (!PROJECT_FOLDER) {
      SetProjectFolder(vscode.workspace.workspaceFolders![0].uri.path);
    }

    let patch = "";
    try {
      patch = readFileSync(PATCH_FOLDER + "/" + params.patchPath, "utf8");
    } catch (err) {
      logging.LogError(err as any);
    }

    let sourceFileMatch = /--- ([^ \n\r\t]+).*/.exec(patch);
    let sourceFile: string;
    if (sourceFileMatch && sourceFileMatch[1]) {
      sourceFile = sourceFileMatch[1];
    } else {
      throw Error("Unable to find source file in '" + params.patchPath + "'");
    }
    let destinationFileMatch = /\+\+\+ ([^ \n\r\t]+).*/.exec(patch);
    let destinationFile;
    if (destinationFileMatch && destinationFileMatch[1]) {
      destinationFile = destinationFileMatch[1];
    } else {
      throw Error(
        "Unable to find destination file in '" + params.patchPath + "'"
      );
    }
    let patched = diff.applyPatch(original, patch);
    return patched;
  }


  async function runOrchestratorOnAFile(javaFilePath: string, progress: any, cancellationToken: any) {
    const pythonExecutable = process.platform === 'win32' ? 'python' : 'python3';
    const args = [
      '/app/orchestrator.py',
      '--single-file',
      javaFilePath
    ];

    // 1) Spawn the process
    const childProc = spawn(pythonExecutable, args, {
    });

    // Handle cancellation
    cancellationToken.onCancellationRequested(() => {
      logging.LogInfo('Cancellation requested. Terminating orchestrator.py...');
      if (process.platform === 'win32') {
        const pid = childProc.pid;
        const exec = require('child_process').exec;
        exec(`taskkill /PID ${pid} /T /F`, (error: any, stdout: any, stderr: any) => {
          if (error) {
            logging.LogError(`Error killing process: ${error.message}`);
          } else {
            logging.LogInfo('Process terminated successfully.');
          }
        });
      } else {
        childProc.kill('SIGINT');
      }
    });

    // Listen for lines from stdout
    const rl = readline.createInterface({
      input: childProc.stdout,
      crlfDelay: Infinity,
    });

    let totalTasks = 0;
    let completedTasks = 0;
    let workflowCompleted = false;
    rl.on('line', (line: string) => {
      logging.LogInfo(`orchestrator.py: ${line}`);

      if (workflowCompleted) {
        return;
      }

      // Remove ANSI escape sequences
      const strippedLine = line.replace(
        /\u001b\[[0-9;]*m/g,
        ''
      );
      const progressMatch = strippedLine.match(/^PROGRESS UPDATE:\s*(\d+)\/(\d+)/);
      if (progressMatch) {
        completedTasks = parseInt(progressMatch[1], 10);
        totalTasks = parseInt(progressMatch[2], 10);

        if (totalTasks > 0) {
          const increment = (1 / totalTasks) * 100;
          progress.report({
            message: `Processing issue ${completedTasks}/${totalTasks}`,
            increment: increment,
          });
        }
      }

      if (strippedLine.toLowerCase().includes('workflow execution completed')) {
        logging.LogInfo('Workflow execution completed detected.');
        workflowCompleted = true;
        progress.report({ increment: 100 });
      }
    });


    childProc.stderr.on('data', (data: Buffer) => {
      const message = data.toString();
      logging.LogInfo(`orchestrator.py: ${message}`);

      if (workflowCompleted) {
        return;
      }

      if (message.toLowerCase().includes('workflow execution completed')) {
        logging.LogInfo('Workflow execution completed detected in stderr.');
        workflowCompleted = true;
        progress.report({ increment: 100 });
      }
    });

    // Handle process exit
    const processExitPromise = new Promise<void>((resolve, reject) => {
      childProc.on('close', (code, signal) => {
        if (cancellationToken.isCancellationRequested) {
          logging.LogInfo('Process was cancelled by the user.');
          resolve();
        } else if (code === 0) {
          logging.LogInfo(`orchestrator.py completed successfully with exit code ${code}`);
          resolve();
        } else {
          const error = new Error(`orchestrator.py exited with code ${code}`);
          logging.LogError(error.message);
          vscode.window.showErrorMessage(`Analysis failed: ${error.message}`);
          progress.report({ increment: 100 });
          reject(error);
        }
      });

      childProc.on('error', (error) => {
        logging.LogError(`Failed to start orchestrator.py: ${error.message}`);
        vscode.window.showErrorMessage(`Failed to start analysis: ${error.message}`);
        progress.report({ increment: 100 });
        reject(error);
      });
    });

    try {
      // Await the process to complete or be cancelled
      await processExitPromise;

      if (cancellationToken.isCancellationRequested) {
        logging.LogInfo('Analysis was cancelled by the user.');
        getDiagnosticsAfterPatch();
        return;
      }

      // 2) Listen for stdout data
      childProc.stdout.on('data', (data) => {
        // data is a Buffer, so convert to string
        const output = data.toString();
        logging.LogInfo(`Orchestrator STDOUT: ${output}`);
      });

      // 3) Listen for stderr data
      childProc.stderr.on('data', (data) => {
        const errorOutput = data.toString();
        logging.LogError(`Orchestrator STDERR: ${errorOutput}`);
      });

      // 4) Listen for the process to exit
      childProc.on('close', (code) => {
        if (code === 0) {
          logging.LogInfo('Orchestrator completed successfully.');
        } else {
          logging.LogError(`Orchestrator exited with code ${code}`);
        }
      });

      // 5) listen for 'error' if spawning fails at the OS level
      childProc.on('error', (err) => {
        logging.LogErrorAndShowErrorMessage('Failed to start orchestrator process', err as any);
      });
    } catch (error) {
      logging.LogError(`Error during analysis: ${error}`);
      progress.report({ increment: 100 }); // Complete the progress bar
      throw error;
    }

    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'Loading Diagnostics...',
      },
      async () => {
        await refreshDiagnosticsWithoutAnalysis();
      }
    );

  }


  async function handleOverlappingIssues(
    jsonFilePath: string,
    patchFilePath: string,
    javaFilePath: string
  ) {
    // 1) Load patch content
    const patchContent = readFileSync(patchFilePath, 'utf8');

    // 2) Parse the patch to get all changed lines
    const parsedDiffs = parsePatch(patchContent);
    const changedLines = new Set<number>();

    for (const singleDiff of parsedDiffs) {
      logging.LogInfo(`Patch modifies file: ${singleDiff.newFileName}`);

      for (const hunk of singleDiff.hunks) {
        let currentNewLine = hunk.newStart;
        for (const line of hunk.lines) {
          if (line.startsWith('-') || line.startsWith('+')) {
            changedLines.add(currentNewLine);
          }
          // Increment new-file line only if it’s not a removal line
          if (!line.startsWith('-')) {
            currentNewLine++;
          }
        }
      }
    }

    logging.LogInfo(`Changed lines from patch: ${[...changedLines].join(', ')}`);

    // 3) Load the JSON issues
    if (!existsSync(jsonFilePath)) {
      logging.LogInfo(`JSON file not found at: ${jsonFilePath}. Skipping overlap handling.`);
      return;
    }

    let allIssues;
    try {
      const jsonRawContent = readFileSync(jsonFilePath, 'utf8');
      allIssues = JSON.parse(jsonRawContent);
    } catch (e) {
      logging.LogErrorAndShowErrorMessage(`Failed to parse JSON from ${jsonFilePath}`, e as any);
      return;
    }

    // 4) For each issue -> item, see if its textRange overlaps any changed line.
    //    We call the orchestrator script only if the item is NOT the same patch
    //    we are currently applying, AND it overlaps the changed lines.

    for (let i = 0; i < allIssues.length; i++) {
      const issue = allIssues[i];
      if (!issue.items) continue;

      for (const item of issue.items) {
        if (!item.textRange) continue;

        // skip calling the orchestrator because it's the patch we just applied.
        let isSamePatch = false;
        if (item.patches && Array.isArray(item.patches)) {
          isSamePatch = item.patches.some(
            (p: any) => p.path === patchFilePath
          );
        }

        // Now check overlap
        const { startLine, endLine } = item.textRange;
        let overlaps = false;
        for (let line = startLine; line <= endLine; line++) {
          if (changedLines.has(line)) {
            overlaps = true;
            break;
          }
        }

        if (overlaps && !isSamePatch) {
          logging.LogInfo(
            `Overlap found for issue ${issue.id} on lines [${startLine}, ${endLine}] -> calling orchestrator.`
          );
          getOutputFromAnalyzerOfAFile(javaFilePath);
        } else if (overlaps && isSamePatch) {
          logging.LogInfo(
            `Overlap found for issue ${issue.id} on lines [${startLine}, ${endLine}] but it's the same patch, skipping orchestrator.`
          );
        }
      }
    }

    return changedLines;

  }

  function getAllPatchPathsFromJson(jsonFilePath: string): string[] {
    const patchPaths: string[] = [];
  
    if (!existsSync(jsonFilePath)) {
      logging.LogInfo(`Cannot find JSON at ${jsonFilePath}, returning empty patch list.`);
      return patchPaths;
    }
  
    const rawContent = readFileSync(jsonFilePath, 'utf8');
    let issues;
    try {
      issues = JSON.parse(rawContent);
    } catch (e) {
      logging.LogInfo(`Could not parse JSON at ${jsonFilePath}, returning empty patch list.`);
      return patchPaths;
    }
  
    // The JSON structure is an array of issues -> each has items[] -> each has patches[]
    for (const issue of issues) {
      if (!issue.items) continue;
      for (const item of issue.items) {
        if (!item.patches || !Array.isArray(item.patches)) continue;
  
        // for each patch in patches
        for (const patchObj of item.patches) {
          if (patchObj.path) {
            patchPaths.push(patchObj.path);
          }
        }
      }
    }
  
    return patchPaths;
  }

  async function handleFuturePatchConflicts(
    newlyAppliedPatchPath: string, 
    changedLines: Set<number>, 
    allDiffPaths: string[],
    javaFilePath: string
  ) {
    logging.LogInfo(`Checking future patch conflicts with: ${newlyAppliedPatchPath}`);
  
    for (const diffPath of allDiffPaths) {
      // Skip the patch we just applied
      if (diffPath === newlyAppliedPatchPath) continue;
  
      if (!existsSync(diffPath)) {
        logging.LogInfo(`Patch file ${diffPath} does not exist, skipping.`);
        continue;
      }
  
      const patchContent = readFileSync(diffPath, 'utf-8');
      const parsedDiffs = parsePatch(patchContent);
  
      let conflictFound = false;
  
      for (const singleDiff of parsedDiffs) {
        // Check if it modifies the same file as javaFilePath
  
        for (const hunk of singleDiff.hunks) {
          let oldLine = hunk.oldStart;
          for (const line of hunk.lines) {
            // `-` or ' ' lines reference the old code that must still be present
            if (line.startsWith('-') || line.startsWith(' ')) {
              if (changedLines.has(oldLine)) {
                conflictFound = true;
                break;
              }
              oldLine++;
            } else if (line.startsWith('+')) {
              // plus-lines are new lines for that patch, skip
            }
          }
          if (conflictFound) break;
        }
        if (conflictFound) break;
      }
  
      if (conflictFound) {
        logging.LogInfo(
          `Patch ${diffPath} may be invalidated by changes in ${newlyAppliedPatchPath}, re-running analyzer.`
        );
        await getOutputFromAnalyzerOfAFile(javaFilePath);
        return;
        
      }
    }
  }

async function applyPatch() {
  logging.LogInfo("===== Executing applyPatch command. =====");

  if (ANALYZER_USE_DIFF_MODE == "view Diffs") {
    const webview = getActiveDiffPanelWebview();

    if ("leftPath" in webview.params && "patchPath" in webview.params) {
      logging.LogInfo("Saving files and fixes to state...");
      await saveFileAndFixesToState(webview.params.leftPath!);

      try {
        await updateUserDecisions("applied", webview.params.patchPath!, webview.params.leftPath!);

        // 1) Apply the patch to the code
        webview.api.applyPatch();

        let openFilePath = vscode.Uri.file(upath.normalize(String(webview.params.leftPath)));
        const document = await vscode.workspace.openTextDocument(openFilePath);
        await vscode.window.showTextDocument(document);

        // 2) Construct the jsonFilePath
        let PROJECT_RELATIVE_PATH;
        if (path.isAbsolute(webview.params.leftPath)) {
          PROJECT_RELATIVE_PATH = path.relative(path.dirname(PATCH_FOLDER), webview.params.leftPath);
        } else {
          PROJECT_RELATIVE_PATH = webview.params.leftPath;
        }
        const jsonFilePath = path.join(
          path.dirname(PATCH_FOLDER),
          'validation',
          'jsons',
          'jsons',
          PROJECT_RELATIVE_PATH
        ) + '.json';

        // 3) Overlapping issues
        logging.LogInfo("1. handleOverlappingIssues");
        const changedLines = await handleOverlappingIssues(
          jsonFilePath, 
          webview.params.patchPath!, 
          webview.params.leftPath!
        );

        // 4) Filter out issues directly connected to the patch we just applied
        await filterOutIssues(webview.params.patchPath!);

        // 5) Update line references for remaining issues
        await updateIssueLinesAfterPatch(webview.params.leftPath!, webview.params.patchPath!);

        // 6) Now check for "future patch conflicts"
        const allDiffPaths = getAllPatchPathsFromJson(jsonFilePath);
        
        await handleFuturePatchConflicts(
          webview.params.patchPath!,
          changedLines as any,
          allDiffPaths,
          webview.params.leftPath!
        );

        // Close the webview, refresh diagnostics, etc.
        activeDiffPanelWebviews.splice(activeDiffPanelWebviews.indexOf(webview), 1);
        if (activeDiffPanelWebviews.length < 1) {
          vscode.commands.executeCommand("setContext", "patchApplyEnabled", false);
        }
        await getDiagnosticsAfterPatch();
      } catch (error) {
        logging.LogErrorAndShowErrorMessage("Error during patch application:", error as any);
      }
    }
  } else if (ANALYZER_USE_DIFF_MODE == "view Patch files") {
    viewPatchFilesMode();
  }

  await refreshDiagnosticsWithoutAnalysis();
}

  async function viewPatchFilesMode(patchPath: string = "") {
    // Get the content of the original file
    let patchFilepath;
    if (!patchPath) {
      patchFilepath = JSON.parse(
        context.workspaceState.get<string>("openedPatchPath")!
      );
    } else {
      patchFilepath = patchPath;
    }
    // console.log("OPENED PATCH PATH:", patchFilepath);

    let patchFileContent = readFileSync(
      path.normalize(patchFilepath),
      "utf8"
    );

    let sourceFilePathMatch = /--- ([^ \n\r\t]+).*/.exec(patchFileContent);
    let sourceFilePath: string;
    if (sourceFilePathMatch && sourceFilePathMatch[1]) {
      sourceFilePath = sourceFilePathMatch[1];
    } else {
      throw Error("Unable to find source file in '" + patchFilepath + "'");
    }

    sourceFilePath = upath.normalize(upath.join(PROJECT_FOLDER, sourceFilePath));
    if (process.platform === "linux" || process.platform === "darwin") {
      if (sourceFilePath[0] !== "/") {
        sourceFilePath = "/" + sourceFilePath;
      }
    }
    // Saving issues.json and file contents in state,
    // so later the changes can be reverted if the user asks for it:
    saveFileAndFixesToState(path.normalize(sourceFilePath));

    let sourceFileContent = readFileSync(path.normalize(sourceFilePath), "utf8");

    // Apply the patch to the original file
    let patched = diff.applyPatch(sourceFileContent, patchFileContent);
    logging.LogInfo(patched);

    // Overwrite the original file with the patched content
    if (patchPath) {
      applyPatchToFile(path.normalize(sourceFilePath), patched, patchFilepath, true);
    } else {
      applyPatchToFile(path.normalize(sourceFilePath), patched, patchFilepath, false);
    }

    updateIssueLinesAfterPatch(sourceFilePath, patchFilepath);

    await getDiagnosticsAfterPatch();

    // Hide navbar buttons (applyPatch, declinePatch, nextDiff, prevDiff)
    vscode.commands.executeCommand("setContext", "patchApplyEnabled", false);
    //getOutputFromAnalyzerOfAFile();
  }

  async function updateIssueLinesAfterPatch(sourceFilePath: string, patchFilePath: string) {
    const patchContent = readFileSync(patchFilePath, "utf8");

    // Parse the applied patch and compute line shifts
    const parsedPatch = diff.parsePatch(patchContent);
    const lineShifts = computeLineShifts(parsedPatch);

    // Update the issues' text ranges in the related JSON file
    updateIssuesTextRanges(sourceFilePath, lineShifts);

    // Find and update all diffs in the corresponding JSON, except the one applied
    updateDiffHeadersInJson(sourceFilePath, patchFilePath, lineShifts);
  }

  function updateDiffHeadersInJson(sourceFilePath: string, appliedPatchFilePath: string, lineShifts: { [lineNumber: number]: number }) {
    // Find the matching JSON file in ISSUES_PATH
    const issuesJsonPaths = getIssuesJsonPathsForSourceFile(sourceFilePath);

    // Get the Java filename from the sourceFilePath
    const sourceFileBaseName = path.basename(sourceFilePath, '.java');

    // Go through each JSON file related to this source file
    issuesJsonPaths.forEach(jsonPath => {
      const jsonContent = readFileSync(jsonPath, 'utf8');
      const issues = JSON.parse(jsonContent);

      let updated = false;

      // Iterate over each issue in the JSON file
      issues.forEach((issue: any) => {
        issue.items.forEach((item: any) => {
          item.patches.forEach((patch: any) => {
            // Skip updating the patch that was just applied (patchFilePath)
            if (patch.path === appliedPatchFilePath || appliedPatchFilePath.includes(patch.path)) {
              return;
            }

            // Apply header updates for other patches
            const patchFilePath = patch.path;
            updateDiffHeaders(patchFilePath, lineShifts);  // Update the diff headers
            updated = true;
          });
        });
      });

      // Write back updated issues if changes were made
      if (updated) {
        writeFileSync(jsonPath, JSON.stringify(issues, null, 2), 'utf8');
      }
    });
  }

  function updateDiffHeaders(patchFilePath: string, lineShifts: { [lineNumber: number]: number }) {
    let patchContent = readFileSync(patchFilePath, 'utf8');
    const parsedPatch = diff.parsePatch(patchContent);

    let updatedPatch = "";

    parsedPatch.forEach((hunk: { hunks: any[]; }) => {
      // Preserve the source lines (`---` and `+++`) from the diff file.
      const sourceLines = patchContent.split('\n').slice(0, 2);
      updatedPatch += sourceLines.join('\n') + "\n"; // Add the source lines back into the patch content

      // Iterate through each hunk and update its header
      hunk.hunks.forEach(chunk => {
        // Adjust the old and new line numbers in the diff header based on the shifts
        const oldStartLine = chunk.oldStart;
        const newStartLine = chunk.newStart;

        let adjustedOldStart = oldStartLine;
        let adjustedNewStart = newStartLine;

        // Apply the shifts
        for (const line in lineShifts) {
          const lineNumber = parseInt(line, 10);
          if (oldStartLine >= lineNumber) {
            adjustedOldStart += lineShifts[lineNumber];
          }
          if (newStartLine >= lineNumber) {
            adjustedNewStart += lineShifts[lineNumber];
          }
        }

        // Replace the header in the patch content with updated line numbers
        const header = `@@ -${adjustedOldStart},${chunk.oldLines} +${adjustedNewStart},${chunk.newLines} @@`;

        // Construct updated patch content by appending the header and chunk lines
        updatedPatch += header + "\n";
        chunk.lines.forEach((line: string) => {
          updatedPatch += line + "\n";
        });
      });
    });

    // Write the updated patch back to the file
    writeFileSync(patchFilePath, updatedPatch, 'utf8');
  }

  function computeLineShifts(parsedPatch: any): { [lineNumber: number]: number } {
    const lineShifts: { [lineNumber: number]: number } = {};
    let cumulativeShift = 0;

    parsedPatch.forEach((hunk: { hunks: any[]; }) => {
      hunk.hunks.forEach(chunk => {
        const startLine = chunk.oldStart;
        const oldLines = chunk.oldLines || 0;
        const newLines = chunk.newLines || 0;
        const lineDiff = newLines - oldLines;

        cumulativeShift += lineDiff;

        lineShifts[startLine] = cumulativeShift;
      });
    });

    return lineShifts;
  }

  function updateIssuesTextRanges(sourceFilePath: string, lineShifts: { [lineNumber: number]: number }) {
    // Load the issues for the source file
    const issuesJsonPaths = getIssuesJsonPathsForSourceFile(sourceFilePath);

    issuesJsonPaths.forEach(jsonPath => {
      const issuesContent = readFileSync(jsonPath, 'utf8');
      const issues = JSON.parse(issuesContent);

      let updated = false;

      issues.forEach((issue: any) => {
        issue.items.forEach((item: any) => {
          const startLine = item.textRange.startLine;
          const endLine = item.textRange.endLine;

          let shift = 0;

          // Determine the shift for the current issue based on the line shifts
          for (const line in lineShifts) {
            const lineNumber = parseInt(line, 10);
            if (startLine > lineNumber) {
              shift = lineShifts[line];
            }
          }

          if (shift !== 0) {
            // Update the text ranges
            item.textRange.startLine += shift;
            item.textRange.endLine += shift;
            updated = true;
          }
        });
      });

      if (updated) {
        // Write back the updated issues
        writeFileSync(jsonPath, JSON.stringify(issues, null, 2), 'utf8');
      }
    });
  }

  function getIssuesJsonPathsForSourceFile(sourceFilePath: string): string[] {
    const issuesPathContent = readFileSync(ISSUES_PATH, "utf8");
    const jsonFilePaths = issuesPathContent
      .split('\n')
      .map(line => line.trim())
      .filter(line => line.length > 0)
      .map(jsonPath => path.resolve(jsonPath));

    const sourceFileBaseName = path.basename(sourceFilePath, '.java');

    const matchingJsonPaths = jsonFilePaths.filter(jsonPath => {
      const jsonBaseName = path.basename(jsonPath, '.json');
      return jsonBaseName.includes(sourceFileBaseName);
    });

    return matchingJsonPaths;
  }

  function declinePatch() {
    if (ANALYZER_USE_DIFF_MODE == "view Diffs") {
      let patchPath = "";
      const webview = getActiveDiffPanelWebview();
      activeDiffPanelWebviews.splice(
        activeDiffPanelWebviews.indexOf(webview),
        1
      );

      if ("leftPath" in webview.params && "patchPath" in webview.params) {
        updateUserDecisions(
          "declined",
          webview.params.patchPath!,
          webview.params.leftPath!
        ).then(() => {
          if ("leftPath" in webview.params && "patchPath" in webview.params) {
            let openFilePath = vscode.Uri.file(
              upath.normalize(String(webview.params.leftPath))
            );
            let projectFolder = PROJECT_FOLDER;
            let leftPath = upath.normalize(webview.params.leftPath);
            if (!leftPath.includes(upath.normalize(String(PROJECT_FOLDER)))) {
              openFilePath = vscode.Uri.file(
                upath.join(PROJECT_FOLDER, leftPath)
              );
            }

            if ("patchPath" in webview.params && webview.params.patchPath) {
              patchPath = webview.params.patchPath;
            }

            testView.treeDataProvider?.refresh(patchPath);
            groupedTestView.treeDataProvider?.refresh(patchPath);

            vscode.workspace.openTextDocument(openFilePath).then((document) => {
              vscode.window.showTextDocument(document).then(() => {
                vscode.window.withProgress(
                  {
                    location: vscode.ProgressLocation.Notification,
                    title: "Loading Diagnostics...",
                  },
                  async () => {
                    await refreshDiagnostics(
                      vscode.window.activeTextEditor!.document,
                      analysisDiagnostics
                    );
                  }
                );
              });
            });
          }
        });
      }

      if (activeDiffPanelWebviews.length < 1) {
        vscode.commands.executeCommand(
          "setContext",
          "patchApplyEnabled",
          false
        );
      }

      webview.webViewPanel.dispose();
    } else if (ANALYZER_USE_DIFF_MODE == "view Patch files") {
      // TODO: DO it with patch file
      let activeEditor = vscode.window.activeTextEditor!.document.uri.fsPath;
      let patchFilepath = JSON.parse(
        context.workspaceState.get<string>("openedPatchPath")!
      );
      let patchFileContent = readFileSync(patchFilepath, "utf8");
      let sourceFileMatch = /--- ([^ \n\r\t]+).*/.exec(patchFileContent);
      let sourceFile: string;
      if (sourceFileMatch && sourceFileMatch[1]) {
        sourceFile = sourceFileMatch[1];
      } else {
        throw Error("Unable to find source file in '" + patchFilepath + "'");
      }

      sourceFile = upath.normalize(upath.join(PROJECT_FOLDER, sourceFile));
      if (process.platform === "linux" || process.platform === "darwin") {
        if (sourceFile[0] !== "/") sourceFile = "/" + sourceFile;
      }

      vscode.commands.executeCommand("setContext", "patchApplyEnabled", false);

      testView.treeDataProvider?.refresh(patchFilepath);
      groupedTestView.treeDataProvider?.refresh(patchFilepath);

      vscode.workspace.openTextDocument(sourceFile).then((document) => {
        vscode.window.showTextDocument(document).then(() => {
          vscode.window.withProgress(
            {
              location: vscode.ProgressLocation.Notification,
              title: "Loading Diagnostics...",
            },
            async () => {
              // 4.
              await refreshDiagnostics(
                vscode.window.activeTextEditor!.document,
                analysisDiagnostics
              );

              updateUserDecisions("declined", patchFilepath, sourceFile);
            }
          );
        });
      });
    }
  }

  async function filterOutIssues(patchPath: String) {
    await initIssues();
    if (issues) {
      const currentFilePath = upath.normalize(
        vscode.window.activeTextEditor!.document.uri.path
      );
      //saveFileAndFixesToState(currentFilePath);

      for (const key of Object.keys(issues)) {
        for (const issue of issues[key]) {
          for (const patch of issue.patches) {
            if (patch.path === patchPath || patchPath.includes(patch.path)) {
              logging.LogInfo(`Removing issue with id: ${issue.id}`);
              const warning_id = issue.id;
              issues[key].splice(issues[key].indexOf(issue), 1);
              if (warning_id) {
                await removeObjectById(warning_id, currentFilePath);
              }
            }
          }
        }
      }
    }

    const issuesStr = stringify(issues);
    logging.LogInfo("from filter out cm.ts " + issuesStr);
  }

  async function removeObjectById(id: string, currentFilePath: string): Promise<[string, string]> {
    try {
      // Create the JSON file path
      const jsonFilePath = createJsonFilePath(currentFilePath);
      // console.log("json path:", jsonFilePath);

      // Read the content of the JSON file
      const fileContent = await fs.readFile(jsonFilePath, 'utf-8');
      // console.log("json content:", fileContent);

      // Parse the JSON content
      let jsonArray;
      try {
        jsonArray = JSON.parse(fileContent);
      } catch (parseError) {
        logging.LogErrorAndShowErrorMessage('Error parsing JSON:', parseError as any);
        throw parseError;
      }

      // Ensure jsonArray is actually an array
      if (!Array.isArray(jsonArray)) {
        throw new Error('Parsed JSON is not an array');
      }

      // console.log("json array:", jsonArray);

      // Filter out the object with the matching ID
      const updatedJsonArray = jsonArray.filter((item: any) => {
        if (item && item.id) {
          console.log("Removed item:", item);
          return item.id !== id;
        } else {
          logging.LogErrorAndShowErrorMessage('Item does not have an id or is undefined:', item);
          return true;
        }
      });

      // Stringify the updated array
      const updatedContent = JSON.stringify(updatedJsonArray, null, 2);
      // console.log("updated array:", updatedContent);

      // Write the updated content back to the JSON file
      await fs.writeFile(jsonFilePath, updatedContent, 'utf-8');

      logging.LogInfo(`Successfully removed the object with id: ${id}`);

      getDiagnosticsAfterPatch();

      // Return the original file content and JSON file path
      return [fileContent, jsonFilePath];
    } catch (error) {
      logging.LogErrorAndShowErrorMessage('Error while processing the file:', error as any);
      throw error; // Re-throw the error if needed
    }
  }


  function createJsonFilePath(currentFilePath: string): string {
    let PROJECT_RELATIVE_PATH;
    if (path.isAbsolute(currentFilePath)) {
      PROJECT_RELATIVE_PATH = path.relative(
        path.dirname(PATCH_FOLDER),
        currentFilePath
      );
    } else {
      PROJECT_RELATIVE_PATH = currentFilePath;
    }

    const jsonFilePath = path.join(
      path.dirname(PATCH_FOLDER),
      'validation',
      'jsons',
      'jsons', // for some reason some path should be here otherwise the 'jsons' won't be included in the final jsonFilePath
      PROJECT_RELATIVE_PATH
    ) + '.json';
    return jsonFilePath;
  }

  async function saveFileAndFixesToState(filePath: string) {
    // Normalize the path correctly
    let normalizedFilePath;

    if (process.platform === "win32") {
      const driveLetterRegex = /^\/([a-zA-Z]):\//;
      if (driveLetterRegex.test(filePath)) {
        normalizedFilePath = filePath.replace(driveLetterRegex, (match, driveLetter) => {
          return `${driveLetter.toUpperCase()}:\\`;
        });
      } else if (/^[a-zA-Z]:/.test(filePath) && filePath.includes('/')) {
        normalizedFilePath = upath.toUnix(filePath).replace(driveLetterRegex, (match: any, driveLetter: string) => {
          return `${driveLetter.toUpperCase()}:\\`;
        });
      }
    } else {
      normalizedFilePath = upath.normalize(filePath);
    }

    logging.LogInfo("Final normalized file path: " + normalizedFilePath);

    let jsonFilePath = createJsonFilePath(normalizedFilePath);

    let originalFileContent = readFileSync(normalizedFilePath, "utf8");
    let originalIssuesContent = readFileSync(jsonFilePath, "utf8");
    context.workspaceState.update(
      "lastFileContent",
      originalFileContent
    );
    context.workspaceState.update("lastFilePath", filePath);

    context.workspaceState.update(
      "lastIssuesContent",
      JSON.stringify(originalIssuesContent)
    );
    context.workspaceState.update("lastIssuesPath", jsonFilePath);
  }

  let currentFixId = 0;

  async function navigateDiff(step: number) {
    if (ANALYZER_USE_DIFF_MODE == "view Diffs") {
      let activeWebview = getActiveDiffPanelWebview();
      let origPath = "";
      let patchPath = "";
      if ("leftPath" in activeWebview.params) {
        origPath = activeWebview.params.leftPath!;
      }
      if ("patchPath" in activeWebview.params) {
        patchPath = activeWebview.params.patchPath!;
      }

      let fixes = await fakeAiFixCode.getFixes(origPath, patchPath);
      let nextFixId = currentFixId + step;
      if (!fixes[nextFixId]) {
        nextFixId = nextFixId > 0 ? 0 : fixes.length - 1;
      }

      let sourceFile = "";
      let requiredWebview = activeDiffPanelWebviews.find((webview) => {
        if ("patchPath" in webview.params) {
          if (webview.params.patchPath! === fixes[nextFixId].path) {
            return webview;
          }
        }
      });

      if (requiredWebview) {
        requiredWebview!.webViewPanel.reveal(vscode.ViewColumn.One, false);
      } else {
        let leftContent = getLeftContent(fixes[nextFixId].path);
        let rightContent = getRightContent(fixes[nextFixId].path, leftContent);
        showDiff({
          patchPath: fixes[nextFixId].path,
          leftContent: leftContent,
          rightContent: rightContent,
          leftPath: origPath,
          rightPath: "",
          context,
        });
      }
      currentFixId = nextFixId;
    } else if (ANALYZER_USE_DIFF_MODE == "view Patch files") {
      let patchFilepath = JSON.parse(
        context.workspaceState.get<string>("openedPatchPath")!
      );
      let patchFileContent = readFileSync(patchFilepath, "utf8");
      let sourceFileMatch = /--- ([^ \n\r\t]+).*/.exec(patchFileContent);
      let sourceFile: string;
      if (sourceFileMatch && sourceFileMatch[1]) {
        sourceFile = sourceFileMatch[1];
      } else {
        throw Error("Unable to find source file in '" + patchFilepath + "'");
      }
      let leftPath = upath.normalize(upath.join(PROJECT_FOLDER, sourceFile));
      if (process.platform === "linux" || process.platform === "darwin") {
        if (leftPath[0] !== "/") leftPath = "/" + leftPath;
      }
      let fixes = await fakeAiFixCode.getFixes(leftPath, patchFilepath);
      let nextFixId = currentFixId + step;
      if (!fixes[nextFixId]) {
        nextFixId = nextFixId > 0 ? 0 : fixes.length - 1;
      }

      let fixPath = upath.normalize(
        upath.join(PATCH_FOLDER, fixes[nextFixId].path)
      );
      if (process.platform === "linux" || process.platform === "darwin") {
        if (fixPath[0] !== "/") fixPath = "/" + fixPath;
      }

      vscode.workspace.openTextDocument(fixPath).then((document) => {
        vscode.window.showTextDocument(document).then(() => {
          context.workspaceState.update(
            "openedPatchPath",
            JSON.stringify(fixPath)
          );
        });
      });
      currentFixId = nextFixId;
    }
  }

  function nextDiff() {
    logging.LogInfo("===== Executing nextDiff command. =====");
    navigateDiff(+1);
    logging.LogInfo("===== Finished nextDiff command. =====");
  }

  function prevDiff() {
    logging.LogInfo("===== Executing nextDiff command. =====");
    navigateDiff(-1);
    logging.LogInfo("===== Finished nextDiff command. =====");
  }

  function isPatchAlreadyOpened(sourceFile: string) {
    return activeDiffPanelWebviews.some((x: ExtendedWebview) => {
      // compiler will not accept x.params.leftPath as a valid property of its own type (ExtendedWebviewEnv), because it is a inherited
      // property. That is the reason we use this if statement.
      if ("leftPath" in x.params) {
        return (
          x.params.leftPath!.substring(
            x.params.leftPath!.lastIndexOf("/") + 1,
            x.params.leftPath!.length
          ) === sourceFile
        );
      }
    });
  }

  function getLeftContent(patchPath: string) {
    if (!PROJECT_FOLDER) {
      SetProjectFolder(vscode.workspace.workspaceFolders![0].uri.path);
    }
    let outputFolder = PATCH_FOLDER;
    if (!outputFolder) {
      outputFolder = vscode.workspace.workspaceFolders![0].uri.path;
    }

    let patch = "";
    try {
      patch = readFileSync(
        upath.normalize(upath.join(outputFolder, patchPath)),
        "utf8"
      );
    } catch (err) {
      logging.LogError(err as any);
    }
    let sourceFileMatch = /--- ([^ \n\r\t]+).*/.exec(patch);
    let sourceFile: string;
    if (sourceFileMatch && sourceFileMatch[1]) {
      sourceFile = sourceFileMatch[1];
    } else {
      throw Error("Unable to find source file in '" + patchPath + "'");
    }

    sourceFile = upath.normalize(upath.join(PROJECT_FOLDER, sourceFile));
    if (process.platform === "linux" || process.platform === "darwin") {
      if (sourceFile[0] !== "/") {
        sourceFile = "/" + sourceFile;
      }
    }

    let original = readFileSync(sourceFile, "utf8");
    return original;
  }

  function getRightContent(patchPath: string, original: string) {
    let outputFolder = PATCH_FOLDER;
    if (!outputFolder) {
      outputFolder = vscode.workspace.workspaceFolders![0].uri.path;
    }

    let patch = "";
    try {
      patch = readFileSync(outputFolder + "/" + patchPath, "utf8");
    } catch (err) {
      logging.LogError(err as any);
    }
    let destinationFileMatch = /\+\+\+ ([^ \n\r\t]+).*/.exec(patch);
    let destinationFile;
    if (destinationFileMatch && destinationFileMatch[1]) {
      destinationFile = destinationFileMatch[1];
    } else {
      throw Error("Unable to find destination file in '" + patchPath + "'");
    }
    let patched = diff.applyPatch(original, patch);

    return patched;
  }
}