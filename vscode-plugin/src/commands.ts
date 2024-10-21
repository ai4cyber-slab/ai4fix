import { showDiff, showNotSupported } from "./webview";
import {
  readFileSync,
  writeFileSync,
  existsSync,
  fstat,
  access,
  watch,
  constants,
  appendFileSync,
  readdirSync,
} from "fs";
import * as vscode from "vscode";
import {
  getActiveDiffPanelWebview,
  getActiveDiffPanelWebviews,
} from "./webview/store";
import {
  ISSUES_PATH,
  TEST_FOLDER,
  PATCH_FOLDER,
  PROJECT_FOLDER,
  ANALYZER_USE_DIFF_MODE,
  SetProjectFolder,
  SCRIPT_PATH,
  utf8Stream,
} from "./constants";
import { IChange, IFix, Iissue, IProjectAnalysis } from "./interfaces";
import {
  ExtendedWebview,
  ExtendedWebviewEnv,
  IExtendedWebviewEnvDiff,
} from "./webview/extendedWebview";
import { refreshDiagnostics } from "./language/diagnostics";
import { TestView } from "./providers/testView";
import { GroupedTestView } from "./providers/testViewGrouped";
import { analysisDiagnostics } from "./extension";
import * as fakeAiFixCode from "./services/fakeAiFixCode";
import * as logging from "./services/logging";
import { SymbolDisplayPartKind, WatchDirectoryFlags } from "typescript";
import { basename, dirname } from "path";
import { applyPatchToFile } from "./patch";
import { getSafeFsPath } from "./path";
import { initActionCommands } from "./language/codeActions";
import * as child_process from 'child_process';

import * as cp from "child_process";


const parseJson = require("parse-json");
const parseDiff = require("parse-diff");
const { applyPatchWithWhitespaceIgnore } = require('../utils/applyPatchWrapper');
const diff = require("diff");
var path = require("path");
var upath = require("upath");
var stringify = require("json-stringify");

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
    logging.LogError("Error reading the issuesPath file: " + err);
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
  logging.LogInfo("issues got from analyzer output: " + JSON.stringify(output));

  logging.LogInfoAndShowInformationMessage(
    "===== Finished analysis. =====",
    "Finished analysis of project!"
  );
}

export function init(
  context: vscode.ExtensionContext,
  jsonOutlineProvider: any
) {
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
    )
  );

  vscode.commands.executeCommand("setContext", "patchApplyEnabled", false);

  function blank() {
    showDiff({ leftContent: "", rightContent: "", rightPath: "", context });
    vscode.commands.executeCommand("setContext", "patchApplyEnabled", true);
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
    logging.LogInfo("===== Analysis started from command. =====");

    vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Analyzing project!",
        cancellable: false,
      },
      async () => {
        return runOrchestratorScript();
      }
    );
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
      logging.LogError("Error reading the issuesPath file: " + err);
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
    logging.LogInfo("issues got from analyzer output: " + JSON.stringify(output));
  
    logging.LogInfoAndShowInformationMessage(
      "===== Finished analysis. =====",
      "Finished analysis of project!"
    );
  }

  function runOrchestratorScript() {
    let issuesPath = ISSUES_PATH;
    try {
      writeFileSync(issuesPath, "", "utf8");
      logging.LogInfo(`Cleared content of the file at ${issuesPath}`);
    } catch (error) {
      logging.LogErrorAndShowErrorMessage(`Failed to clear content of the file at ${issuesPath}:`, error as any);
    }
    let generatedPatchesPath = PATCH_FOLDER;
    let subjectProjectPath = PROJECT_FOLDER;
    let jsonFilePaths: string[] = [];

    return new Promise<void>((resolve, reject) => {
      const scriptPath = upath.normalize(upath.join(SCRIPT_PATH, 'orchestrator.py'));
  
      const pythonCommand = process.platform === 'win32' ? 'python' : 'python3';
      const command = `${pythonCommand} "${scriptPath}"`;
  
      const options: child_process.ExecOptions = {
        cwd: PROJECT_FOLDER,
        shell: process.platform === 'win32' ? 'cmd.exe' : '/bin/sh',
      };
  
      logging.LogInfo(`Running orchestrator in: ${PROJECT_FOLDER}`);
  
      // Execute the command
      const childProc = child_process.exec(command, options, (error, stdout, stderr) => {
        if (error) {
          logging.LogErrorAndShowErrorMessage("Error running orchestrator.py", error.message);
          reject(error);
          return;
        }
  
        if (stderr) {
          logging.LogError(`orchestrator.py stderr: ${stderr}`);
        }
  
        logging.LogInfo(`orchestrator.py output: ${stdout}`);
        resolve();
      });
  
      childProc.stdout?.on('data', (data) => {
        logging.LogInfo(`orchestrator.py: ${data}`);
      });
  
      childProc.stderr?.on('data', (data) => {
        logging.LogError(`orchestrator.py error: ${data}`);
      });
    })
      .then(() => {
    // var currentFilePath = upath.normalize(vscode.window.activeTextEditor!.document.uri.path);
    // if (process.platform === "win32" && currentFilePath.startsWith("/")) {
    //   currentFilePath = currentFilePath.substring(1);
    // }

    try {
      const data = readFileSync(issuesPath, "utf8");
      let lines = data.split("\n");

      jsonFilePaths = lines.filter((line: string) => line.trim().endsWith('.json'));

      if (jsonFilePaths.length === 0) {
        logging.LogError("No JSON file paths found in the issuesPath file.");
        return;
      }
    } catch (err) {
      logging.LogError("Error reading the issuesPath file: " + err);
      return;
    }

    return new Promise<void>((resolve) => {
      // // Get Output from analyzer:
      // let output = fakeAiFixCode.getIssuesSync();
      // logging.LogInfo("issues got from analyzer output: " + JSON.stringify(output));

      // Show issues treeView:
      testView = new TestView(context);
      groupedTestView= new GroupedTestView(context);

      // Initialize action commands of diagnostics made after analysis:
      initActionCommands(context);

      vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: "Loading Diagnostics...",
        },
        async () => {
          await refreshDiagnostics(vscode.window.activeTextEditor!.document, analysisDiagnostics);
        }
      );

            
      let output = fakeAiFixCode.getIssuesSync();
      logging.LogInfo(
        "issues got from analyzer output: " + JSON.stringify(output)
    );

      resolve();
      logging.LogInfoAndShowInformationMessage(
        "===== Finished analysis. =====",
        "Finished analysis of project!"
      );
    });
    })
     .catch((err) => {
      logging.LogError(`Error during analysis: ${err}`);
    });
  }

  async function getOutputFromAnalyzerOfAFile() {
    logging.LogInfo("===== Analysis of a file started from command. =====");
    vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: "Analyzing file!",
        cancellable: false,
      },
      async () => {
        return await startAnalyzingFileSync();
      }
    );
  }

  async function undoLastFix() {
    logging.LogInfo("===== Undo Last Fix started from command. =====");
  
    // Retrieve the last file path
    let lastFilePath = context.workspaceState.get<string>("lastFilePath")!;
  
    // Correct the file path for Windows systems
    if (process.platform === "win32") {
      // Remove any leading '/c:/' or '\\c:\\'
      lastFilePath = lastFilePath.replace(/^([/\\])?c:[/\\]/i, 'C:\\');
    }
  
    // Normalize the path after the correction
    lastFilePath = path.normalize(lastFilePath);
    logging.LogInfo("Corrected file path: " + lastFilePath);
  
    // Get the file content to revert
    const lastFileContent = context.workspaceState.get<string>("lastFileContent")!;
    const lastIssuesPath = path.normalize(context.workspaceState.get<string>("lastIssuesPath")!);
    const lastIssuesContent = JSON.parse(context.workspaceState.get<string>("lastIssuesContent")!);
  
    writeFileSync(lastIssuesPath, lastIssuesContent);
  
    writeFileSync(lastFilePath, lastFileContent);
  
    vscode.workspace.openTextDocument(lastFilePath).then((document) => {
      vscode.window.showTextDocument(document).then(() => {
        if (ANALYZER_USE_DIFF_MODE == "view Diffs") {
          var webview = getActiveDiffPanelWebview();
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
              async () => {
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
              }
              await vscode.commands.executeCommand('workbench.action.closeActiveEditor');
              const document = await vscode.workspace.openTextDocument(lastFilePath as any);
              await vscode.window.showTextDocument(document);
            });
          }
        } else if (ANALYZER_USE_DIFF_MODE == "view Patch files") {
          var patchFilepath = path.normalize(
            JSON.parse(context.workspaceState.get<string>("openedPatchPath")!)
          );
          // Update user decisions of the revert fix:
          updateUserDecisions(
            "Undo was requested by user.",
            patchFilepath,
            lastFilePath
          ).then(async () => {
            getOutputFromAnalyzerOfAFile();
            await vscode.commands.executeCommand('workbench.action.closeActiveEditor');

            const document = await vscode.workspace.openTextDocument(lastFilePath as any);
            await vscode.window.showTextDocument(document);
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
  
      const appliedPatchContent = readFileSync(upath.join(PATCH_FOLDER, appliedPatchFilePath), 'utf8');
      const appliedParsedPatch = diff.parsePatch(appliedPatchContent);
      const appliedLineShifts = computeLineShifts(appliedParsedPatch);
  
      issues.forEach((issue: any) => {
        issue.items.forEach((item: any) => {
          item.patches.forEach((patch: any) => {
            const patchFilePath = upath.join(PATCH_FOLDER, patch.path);
  
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

  function startAnalyzingProjectSync() {
    let issuesPath = ISSUES_PATH;
    let generatedPatchesPath = PATCH_FOLDER;
    let subjectProjectPath = PROJECT_FOLDER;
    let jsonFilePaths: string | any[] = [];

    var currentFilePath = upath.normalize(
      vscode.window.activeTextEditor!.document.uri.path
    );
    if (process.platform === "win32" && currentFilePath.startsWith("/")) {
      currentFilePath = currentFilePath.substring(1);
    }

    try {
      const data = readFileSync(issuesPath, "utf8");
      let lines = data.split("\n");

      jsonFilePaths = lines.filter((line: string) => line.trim().endsWith('.json'));

      if (jsonFilePaths.length === 0) {
        logging.LogError("No JSON file paths found in the issuesPath file.");
        return;
      }
    } catch (err) {
      logging.LogError("Error reading the issuesPath file: " + err);
      return;
    }

    return new Promise<void>((resolve) => {
      // Get Output from analyzer:
      let output = fakeAiFixCode.getIssuesSync();
      logging.LogInfo("issues got from analyzer output: " + JSON.stringify(output));

      // Show issues treeView:
      // tslint:disable-next-line: no-unused-expression
      testView = new TestView(context);
      groupedTestView= new GroupedTestView(context);

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
      var currentFilePath = upath.normalize(
        vscode.window.activeTextEditor!.document.uri.path
      );

      let issuesPath = ISSUES_PATH;
      let generatedPatchesPath = PATCH_FOLDER;
      let subjectProjectPath = PROJECT_FOLDER;

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
      logging.LogInfo(
        "issues got from analyzer output: " + JSON.stringify(output)
      );

      // Show issues treeView:
      // tslint:disable-next-line: no-unused-expression
      testView = new TestView(context);
      groupedTestView= new GroupedTestView(context);

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
          logging.LogInfo("Reading patch from " + PATCH_FOLDER + "/" + patchPath);
          patch = readFileSync(upath.join(PATCH_FOLDER, patchPath), "utf8");
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

          await refreshDiagnostics(document, analysisDiagnostics);

          if (textRange) {
            //await highlightIssueInEditor(textRange);
          }
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

      var patch = "";
      try {
        patch = readFileSync(path.join(PATCH_FOLDER, patchPath), "utf8");
      } catch (err) {
        logging.LogErrorAndShowErrorMessage(
          String(err),
          "Unable to read patch file: " + err
        );
      }

      var sourceFileMatch = /--- ([^ \n\r\t]+).*/.exec(patch);
      var sourceFile: string;
      if (sourceFileMatch && sourceFileMatch[1]) {
        sourceFile = sourceFileMatch[1];
      } else {
        logging.LogErrorAndShowErrorMessage(
          "Unable to find source file in '" + patchPath + "'",
          "Unable to find source file in '" + patchPath + "'"
        );
        throw Error("Unable to find source file in '" + patchPath + "'");
      }
      var destinationFileMatch = /\+\+\+ ([^ \n\r\t]+).*/.exec(patch);
      var destinationFile;
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

      var original = readFileSync(sourceFile, "utf8");
      var patched = applyPatchWithWhitespaceIgnore(original, patch);

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
        .openTextDocument(path.join(PATCH_FOLDER, patchPath))
        .then((document) => {
          context.workspaceState.update(
            "openedPatchPath",
            JSON.stringify(path.join(PATCH_FOLDER, patchPath))
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

    var patch = "";
    try {
      patch = readFileSync(PATCH_FOLDER + "/" + params.patchPath, "utf8");
    } catch (err) {
      logging.LogError(err as any);
    }

    var sourceFileMatch = /--- ([^ \n\r\t]+).*/.exec(patch);
    var sourceFile: string;
    if (sourceFileMatch && sourceFileMatch[1]) {
      sourceFile = sourceFileMatch[1];
    } else {
      throw Error("Unable to find source file in '" + params.patchPath + "'");
    }
    var destinationFileMatch = /\+\+\+ ([^ \n\r\t]+).*/.exec(patch);
    var destinationFile;
    if (destinationFileMatch && destinationFileMatch[1]) {
      destinationFile = destinationFileMatch[1];
    } else {
      throw Error(
        "Unable to find destination file in '" + params.patchPath + "'"
      );
    }
    var patched = diff.applyPatch(original, patch);
    return patched;
  }

  async function applyPatch() {
    logging.LogInfo("===== Executing applyPatch command. =====");
    let openFilePath

    if (ANALYZER_USE_DIFF_MODE == "view Diffs") {
      let patchPath = "";
      const webview = getActiveDiffPanelWebview();
    
      if ("leftPath" in webview.params && "patchPath" in webview.params) {
        // Saving issues.json and file contents in state,
        // so later the changes can be reverted if the user asks for it:
        if ("leftPath" in webview.params) {
          logging.LogInfo("saveFileAndFixesToState RUNNING")
          await saveFileAndFixesToState(webview.params.leftPath!);
          logging.LogInfo("saveFileAndFixesToState RAN")
        }
    
        // Update user decisions
        try {
          await updateUserDecisions(
            "applied",
            webview.params.patchPath!,
            webview.params.leftPath!
          );
    
          // Apply the patch
          webview.api.applyPatch();

          
    
          openFilePath = vscode.Uri.file(
            upath.normalize(String(webview.params.leftPath))
          );
    
          let leftPath = upath.normalize(webview.params.leftPath);
          if (!leftPath.includes(upath.normalize(String(PROJECT_FOLDER)))) {
            openFilePath = vscode.Uri.file(
              upath.join(PROJECT_FOLDER, leftPath)
            );
          }
    
          // Open and show the document
          const document = await vscode.workspace.openTextDocument(openFilePath);
          await vscode.window.showTextDocument(document);
    
          // Filter out issues and update patch headers
          await filterOutIssues(webview.params.patchPath!);
          await updateIssuesAfterPatch(webview.params.leftPath!, webview.params.patchPath!);
    
          // Refresh diagnostics
          await vscode.window.withProgress(
            {
              location: vscode.ProgressLocation.Notification,
              title: "Loading Diagnostics...",
            },
            async () => {
              await refreshDiagnosticsWithoutAnalysis();
            }
          );
    
          // Close the webview and update context
          activeDiffPanelWebviews.splice(
            activeDiffPanelWebviews.indexOf(webview),
            1
          );
          if (activeDiffPanelWebviews.length < 1) {
            vscode.commands.executeCommand(
              "setContext",
              "patchApplyEnabled",
              false
            );
          }
    
          if ("patchPath" in webview.params && webview.params.patchPath) {
            patchPath = webview.params.patchPath;
          }
        } catch (error) {
          logging.LogErrorAndShowErrorMessage("Error during patch application:", error as any);
        }
      }
      

    } else if (ANALYZER_USE_DIFF_MODE == "view Patch files") {
      // 1. Get the content of the original file
      // 2. Apply the patch to it's content.
      // 3. Overwrite at the original file path with the patched content.
      // 4. Hide navbar buttons (applyPatch, declinePatch, nextDiff, prevDiff).

      // 1.
      var patchFilepath = JSON.parse(
        context.workspaceState.get<string>("openedPatchPath")!
      );
      var patchFileContent = readFileSync(
        path.normalize(patchFilepath),
        "utf8"
      );
      var sourceFileMatch = /--- ([^ \n\r\t]+).*/.exec(patchFileContent);
      var sourceFile: string;
      if (sourceFileMatch && sourceFileMatch[1]) {
        sourceFile = sourceFileMatch[1];
      } else {
        throw Error("Unable to find source file in '" + patchFilepath + "'");
      }

      let projectFolder = PROJECT_FOLDER;
      sourceFile = upath.normalize(upath.join(PROJECT_FOLDER, sourceFile));
      if (process.platform === "linux" || process.platform === "darwin") {
        if (sourceFile[0] !== "/") {
          sourceFile = "/" + sourceFile;
        }
      }
      // Saving issupath.join(projectFolder, sourceFile)es.json and file contents in state,
      // so later the changes can be reverted if user asks for it:
      saveFileAndFixesToState(path.normalize(sourceFile));

      var sourceFileContent = readFileSync(path.normalize(sourceFile), "utf8");

      // 2.
      var destinationFileMatch = /\+\+\+ ([^ \n\r\t]+).*/.exec(
        patchFileContent
      );
      var destinationFile;
      if (destinationFileMatch && destinationFileMatch[1]) {
        destinationFile = destinationFileMatch[1];
      } else {
        throw Error(
          "Unable to find destination file in '" + patchFilepath + "'"
        );
      }
      var patched = diff.applyPatch(sourceFileContent, patchFileContent);

      logging.LogInfo(patched);

      // 3.
      applyPatchToFile(path.normalize(sourceFile), patched, patchFilepath);

      filterOutIssues(patchFilepath);

      updateIssuesAfterPatch(sourceFile, patchFilepath);

      getDiagnosticsAfterPatch()

      // 4.
      vscode.commands.executeCommand("setContext", "patchApplyEnabled", false);
      getOutputFromAnalyzerOfAFile();

    }
    await vscode.commands.executeCommand('workbench.action.closeActiveEditor');

    const document = await vscode.workspace.openTextDocument(openFilePath as any);
    await vscode.window.showTextDocument(document);
    logging.LogInfo("===== Finished applyPatch command. =====");
  }


  async function updateIssuesAfterPatch(sourceFilePath: string, patchFilePath: string) {
    const patchContent = readFileSync(upath.join(PATCH_FOLDER, patchFilePath), "utf8");
    
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
              return;  // Skip the applied patch
            }

            // Apply header updates for other patches
            const patchFilePath = upath.join(PATCH_FOLDER, patch.path);
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
      const sourceLines = patchContent.split('\n').slice(0, 2); // First two lines are `---` and `+++`
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
          updatedPatch += line + "\n";  // Add each line in the chunk
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
            var openFilePath = vscode.Uri.file(
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
      var patchFilepath = JSON.parse(
        context.workspaceState.get<string>("openedPatchPath")!
      );
      var patchFileContent = readFileSync(patchFilepath, "utf8");
      var sourceFileMatch = /--- ([^ \n\r\t]+).*/.exec(patchFileContent);
      var sourceFile: string;
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
      const webview = getActiveDiffPanelWebview();
      const currentFilePath = upath.normalize(
        vscode.window.activeTextEditor!.document.uri.path
      );
      saveFileAndFixesToState(currentFilePath);
  
      for (const key of Object.keys(issues)) {
        for (const issue of issues[key]) {
          for (const patch of issue.patches) {
            if (patch.path === patchPath || patchPath.includes(patch.path)) {
              logging.LogInfoAndShowInformationMessage("Removing issue with id: ", issue.id);
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
      
      // Read the content of the JSON file
      const fileContent = await fs.readFile(jsonFilePath, 'utf-8');
      
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
  
      // Filter out the object with the matching ID
      const updatedJsonArray = jsonArray.filter((item: any) => {
        if (item && item.id) {
          return item.id !== id;
        } else {
          logging.LogErrorAndShowErrorMessage('Item does not have an id or is undefined:', item);
          return true;
        }
      });
  
      // Stringify the updated array
      const updatedContent = JSON.stringify(updatedJsonArray, null, 2);
  
      // Write the updated content back to the JSON file
      await fs.writeFile(jsonFilePath, updatedContent, 'utf-8');
  
      logging.LogInfoAndShowInformationMessage("Successfully removed the object with id:", id);

      getDiagnosticsAfterPatch();
  
      // Return the original file content and JSON file path
      return [fileContent, jsonFilePath];
    } catch (error) {
      logging.LogErrorAndShowErrorMessage('Error while processing the file:', error as any);
      throw error; // Re-throw the error if needed
    }
  }
  

function createJsonFilePath(currentFilePath: string): string {
  const SRC_PATH = currentFilePath.substring(currentFilePath.indexOf('src'));
  const json_file_path = path.join(path.dirname(PATCH_FOLDER), 'validation', 'jsons', SRC_PATH) + '.json';
  return json_file_path;
}

async function saveFileAndFixesToState(filePath: string) {
  // Normalize the path correctly
  let normalizedFilePath = filePath;

  // For Windows, remove '/c:/' if it's part of the file path
  if (process.platform === "win32") {
    if (normalizedFilePath.startsWith('/c:/')) {
      normalizedFilePath = normalizedFilePath.replace('/c:/', 'C:\\');
    } else if (normalizedFilePath.startsWith('C:') && normalizedFilePath.includes('/')) {
      // Handle mixed slashes (both C: and /)
      normalizedFilePath = upath.toUnix(normalizedFilePath).replace('/c:/', 'C:\\');
    }
  } else {
    // For Unix systems, normalize as needed
    normalizedFilePath = upath.normalize(filePath);
  }

  logging.LogInfo("Final normalized file path: " + normalizedFilePath);

  // Now, use the corrected file path to read the file contents
  let jsonFilePath = createJsonFilePath(normalizedFilePath);

  // Now, using the corrected file path to read the file contents
  var originalFileContent = readFileSync(normalizedFilePath, "utf8");
  var originalIssuesContent = readFileSync(jsonFilePath, "utf8");
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
    logging.LogInfo(filePath);
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
      var patchFilepath = JSON.parse(
        context.workspaceState.get<string>("openedPatchPath")!
      );
      var patchFileContent = readFileSync(patchFilepath, "utf8");
      var sourceFileMatch = /--- ([^ \n\r\t]+).*/.exec(patchFileContent);
      var sourceFile: string;
      if (sourceFileMatch && sourceFileMatch[1]) {
        sourceFile = sourceFileMatch[1];
      } else {
        throw Error("Unable to find source file in '" + patchFilepath + "'");
      }
      var leftPath = upath.normalize(upath.join(PROJECT_FOLDER, sourceFile));
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

    var patch = "";
    try {
      patch = readFileSync(
        upath.normalize(upath.join(outputFolder, patchPath)),
        "utf8"
      );
    } catch (err) {
      logging.LogError(err as any);
    }
    var sourceFileMatch = /--- ([^ \n\r\t]+).*/.exec(patch);
    var sourceFile: string;
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

    var original = readFileSync(sourceFile, "utf8");
    return original;
  }

  function getRightContent(patchPath: string, original: string) {
    let outputFolder = PATCH_FOLDER;
    if (!outputFolder) {
      outputFolder = vscode.workspace.workspaceFolders![0].uri.path;
    }

    var patch = "";
    try {
      patch = readFileSync(outputFolder + "/" + patchPath, "utf8");
    } catch (err) {
      logging.LogError(err as any);
    }
    var destinationFileMatch = /\+\+\+ ([^ \n\r\t]+).*/.exec(patch);
    var destinationFile;
    if (destinationFileMatch && destinationFileMatch[1]) {
      destinationFile = destinationFileMatch[1];
    } else {
      throw Error("Unable to find destination file in '" + patchPath + "'");
    }
    var patched = diff.applyPatch(original, patch);

    return patched;
  }
}