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
  ANALYZER_EXE_PATH,
  PATCH_FOLDER,
  PROJECT_FOLDER,
  ANALYZER_PARAMETERS,
  ANALYZER_USE_DIFF_MODE,
  SetProjectFolder,
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
import { analysisDiagnostics } from "./extension";
import * as fakeAiFixCode from "./services/fakeAiFixCode";
import * as logging from "./services/logging";
import { SymbolDisplayPartKind, WatchDirectoryFlags } from "typescript";
import { basename, dirname } from "path";
import { applyPatchToFile } from "./patch";
import { getSafeFsPath } from "./path";
import { initActionCommands } from "./language/codeActions";

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

let issues: any;

async function initIssues() {
  issues = await fakeAiFixCode.getIssues();
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
      "aifix4seccode-vscode.redoLastFix",
      redoLastFix
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
        return startAnalyzingProjectSync();
      }
    );
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

  async function redoLastFix() {
    logging.LogInfo("===== Redo Last Fix started from command. =====");

    var lastFilePath = path.normalize(
      JSON.parse(context.workspaceState.get<string>("lastFilePath")!)
    );
    var lastFileContent = JSON.parse(
      context.workspaceState.get<string>("lastFileContent")!
    );
    var lastIssuesPath = path.normalize(
      JSON.parse(context.workspaceState.get<string>("lastIssuesPath")!)
    );
    var lastIssuesContent = JSON.parse(
      context.workspaceState.get<string>("lastIssuesContent")!
    );

    // Set content of issues:
    writeFileSync(lastIssuesPath, lastIssuesContent);

    // Set content of edited file and focus on it:
    writeFileSync(lastFilePath, lastFileContent);

    vscode.workspace.openTextDocument(lastFilePath).then((document) => {
      vscode.window.showTextDocument(document).then(() => {
        if (ANALYZER_USE_DIFF_MODE == "view Diffs") {
          var webview = getActiveDiffPanelWebview();
          if ("patchPath" in webview.params) {
            // Update user decisions of the revert fix:
            updateUserDecisions(
              "Undo was requested by user.",
              path.normalize(webview.params.patchPath!),
              lastFilePath
            ).then(() => {
              getOutputFromAnalyzerOfAFile();
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
          ).then(() => {
            getOutputFromAnalyzerOfAFile();
          });
        }
      });
    });

    logging.LogInfo("===== Redo Last Fix command finished executing. =====");
  }

  function startAnalyzingProjectSync() {
    let issuesPath = vscode.workspace
      .getConfiguration()
      .get<string>("aifix4seccode.analyzer.issuesPath") ?? "";

    let generatedPatchesPath = vscode.workspace
      .getConfiguration()
      .get<string>("aifix4seccode.analyzer.generatedPatchesPath") ?? "";

    let subjectProjectPath = vscode.workspace
      .getConfiguration()
      .get<string>("aifix4seccode.analyzer.subjectProjectPath") ?? "";

    let pythonScriptPath = vscode.workspace
      .getConfiguration()
      .get<string>("aifix4seccode.analyzer.pythonScriptPath") ?? "";
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
      if (!ANALYZER_EXE_PATH) {
        logging.LogErrorAndShowErrorMessage(
          "Unable to run analyzer! Analyzer executable path is missing.",
          "Unable to run analyzer! Analyzer executable path is missing."
        );
        resolve();
      } else if (!ANALYZER_PARAMETERS) {
        logging.LogErrorAndShowErrorMessage(
          "Unable to run analyzer! Analyzer parameters are missing.",
          "Unable to run analyzer! Analyzer parameters are missing."
        );
        resolve();
      } else {
        // run analyzer with terminal (read params and analyzer path from config):
        logging.LogInfo("Analyzer executable started.");
        logging.LogInfo("Running " + ANALYZER_PARAMETERS);
        let fullPathToPythonScript = path.join(pythonScriptPath, 'aifix.py');
        var child = cp.exec(
          `python "${fullPathToPythonScript}" "" "${jsonFilePaths}" "${generatedPatchesPath}" "${subjectProjectPath}" "${ANALYZER_PARAMETERS}" "${ANALYZER_EXE_PATH}"`,
          { cwd: ANALYZER_EXE_PATH },
          (error: { toString: () => string; }) => {
            if (error) {
              logging.LogErrorAndShowErrorMessage(
                error.toString(),
                "Unable to run analyzer! " + error.toString()
              );
            }
          }
        );
        child.stdout.pipe(process.stdout);
        // waiting for analyzer to finish, only then read the output.
        child.on("exit", function () {
          // if executable has finished:
          logging.LogInfo("Analyzer executable finished.");
          // Get Output from analyzer:
          let output = fakeAiFixCode.getIssuesSync();
          logging.LogInfo(
            "issues got from analyzer output: " + JSON.stringify(output)
          );

          // Show issues treeView:
          // tslint:disable-next-line: no-unused-expression
          testView = new TestView(context);

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
      let pythonScriptPath = await getConfigSetting("aifix4seccode.analyzer.pythonScriptPath", "Python script path is not set in the extension settings.");
      const testFolderPath = await getConfigSetting("aifix4seccode.analyzer.testFolderPath", "Test folder path is not set in the extension settings.");
      const generatedPatchesPath = await getConfigSetting("aifix4seccode.analyzer.generatedPatchesPath", "Generated patches path is not set in the extension settings.");
      pythonScriptPath = path.join(pythonScriptPath, 'GPTTest.py');
      await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: "Generating test...",
          cancellable: false,
        },
        async () => {
          const generatedTestFilePath = await generateAndSaveTest(filePath, pythonScriptPath, testFolderPath, generatedPatchesPath);
          vscode.window.showInformationMessage(`Test file created: ${generatedTestFilePath}`);
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
    const fileExtension = path.extname(filePath);
    const baseFileName = path.basename(filePath, fileExtension);
    const generatedTestFileName = `${baseFileName}AITest${fileExtension}`;
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
      console.error('Generated test may be empty.');
      return '';
    }

    return testCode.substring(startIndex + codeBlockStart.length, endIndex).trim();
  }

  async function getConfigSetting(settingKey: string, errorMessage: string): Promise<string> {
    const settingValue = vscode.workspace.getConfiguration().get<string>(settingKey);
    if (!settingValue) {
      vscode.window.showErrorMessage(errorMessage);
      throw new Error(errorMessage);
    }
    return settingValue;
  }

  let retryCount = 0;
  async function runGeneratedTest(filePath: string) {
    let subjectProjectPath = vscode.workspace.getConfiguration().get("aifix4seccode.analyzer.subjectProjectPath");
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
        const testClassName = path.basename(filePath, '.java') + 'AITest';
        const testPath = path.join(subjectProjectPath, "core");

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
          console.error("Error during running the python script:", stderr);
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
      if (!ANALYZER_EXE_PATH) {
        logging.LogErrorAndShowErrorMessage(
          "Unable to run analyzer! Analyzer executable path is missing.",
          "Unable to run analyzer! Analyzer executable path is missing."
        );
        resolve();
      } else if (!ANALYZER_PARAMETERS) {
        logging.LogErrorAndShowErrorMessage(
          "Unable to run analyzer! Analyzer parameters are missing.",
          "Unable to run analyzer! Analyzer parameters are missing."
        );
        resolve();
      } else {
        var currentFilePath = upath.normalize(
          vscode.window.activeTextEditor!.document.uri.path
        );

        let issuesPath = vscode.workspace
          .getConfiguration()
          .get<string>("aifix4seccode.analyzer.issuesPath") ?? "";

        let generatedPatchesPath = vscode.workspace
          .getConfiguration()
          .get<string>("aifix4seccode.analyzer.generatedPatchesPath") ?? "";

        let subjectProjectPath = vscode.workspace
          .getConfiguration()
          .get<string>("aifix4seccode.analyzer.subjectProjectPath") ?? "";

        let pythonScriptPath = vscode.workspace
          .getConfiguration()
          .get<string>("aifix4seccode.analyzer.pythonScriptPath") ?? "";

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

        // run analyzer with terminal (read params and analyzer path from config):
        logging.LogInfo("Analyzer executable started.");
        logging.LogInfo("Running " + ANALYZER_PARAMETERS + " -cu=" + currentFilePath);

        let fullPathToPythonScript = path.join(pythonScriptPath, 'aifix.py');
        var child = cp.exec(
          `python "${fullPathToPythonScript}" "${currentFilePath}" "${jsonFilePath}" "${generatedPatchesPath}" "${subjectProjectPath}" "${ANALYZER_PARAMETERS}" "${ANALYZER_EXE_PATH}"`,
          { cwd: ANALYZER_EXE_PATH },
          (error: { toString: () => string; }) => {
            if (error) {
              logging.LogErrorAndShowErrorMessage(
                error.toString(),
                "Unable to run Python script! " + error.toString()
              );
            }
          }
        );

        child.stdout.pipe(process.stdout);
        // waiting for analyzer to finish, only then read the output.
        child.on("exit", function () {
          // if executable has finished:
          logging.LogInfo("Analyzer executable finished.");
          // Get Output from analyzer:
          let output = fakeAiFixCode.getIssuesSync(currentFilePath);
          logging.LogInfo(
            "issues got from analyzer output: " + JSON.stringify(output)
          );

          // Show issues treeView:
          // tslint:disable-next-line: no-unused-expression
          testView = new TestView(context);

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
    });
  }

  async function openUpFile(patchPath: string) {
    logging.LogInfo("===== Executing openUpFile command. =====");
  
    let project_folder = PROJECT_FOLDER;
    let patch_folder = PATCH_FOLDER;
    if (!PROJECT_FOLDER) {
      SetProjectFolder(vscode.workspace.workspaceFolders![0].uri.path);
    }
  
    var patch = "";
    try {
      logging.LogInfo("Reading patch from " + PATCH_FOLDER + "/" + patchPath);
      patch = readFileSync(upath.join(PATCH_FOLDER, patchPath), "utf8");
    } catch (err) {
      logging.LogErrorAndShowErrorMessage(
        String(err),
        "Unable to read in patch file: " + err
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
    var openFilePath = vscode.Uri.file(
      upath.normalize(upath.join(PROJECT_FOLDER, sourceFile))
    );
  
    logging.LogInfo("Running diagnosis in opened file...");
    vscode.workspace.openTextDocument(openFilePath).then((document) => {
      vscode.window.showTextDocument(document).then(async () => {
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
            await setIssueSelectionInEditor(patchPath);
  
            const editor = vscode.window.activeTextEditor;
            if (editor) {
              const selection = editor.selection;
              editor.revealRange(
                selection,
                vscode.TextEditorRevealType.InCenter
              );
            }
          }
        );
      });
    });
    logging.LogInfo("===== Finished openUpFile command. =====");
  }

  async function setIssueSelectionInEditor(patchPath: string) {
    await initIssues();
    let targetTextRange: any = {};

    Object.values(issues).forEach((issueArrays: any) => {
      issueArrays.forEach((issueArray: any) => {
        if (issueArray["patches"].some((x: any) => x["path"] === patchPath)) {
          targetTextRange = issueArray["textRange"];
        }
      });
    });

    const editor = vscode.window.activeTextEditor;
    const position = editor?.selection.active;

    var newSelection = new vscode.Selection(
      targetTextRange["startLine"] - 1,
      targetTextRange["startColumn"],
      targetTextRange["endLine"] - 1,
      targetTextRange["endColumn"]
    );
    editor!.selection = newSelection;
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
      console.log(err);
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

  function applyPatch() {
    logging.LogInfo("===== Executing applyPatch command. =====");

    if (ANALYZER_USE_DIFF_MODE == "view Diffs") {
      let patchPath = "";
      const webview = getActiveDiffPanelWebview();
      //let wasM = getPatchedContent(webview.params.leftContent, webview.params);

      if ("leftPath" in webview.params && "patchPath" in webview.params) {
        updateUserDecisions(
          "applied",
          webview.params.patchPath!,
          webview.params.leftPath!
        ).then(() => {
          if ("leftPath" in webview.params && "patchPath" in webview.params) {
            // Saving issues.json and file contents in state,
            // so later the changes can be reverted if user asks for it:
            if ("leftPath" in webview.params) {
              saveFileAndFixesToState(webview.params.leftPath!);
            }

            webview.api.applyPatch();

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

            vscode.workspace.openTextDocument(openFilePath).then((document) => {
              vscode.window.showTextDocument(document).then(() => {
                if (
                  "leftPath" in webview.params &&
                  "patchPath" in webview.params
                ) {
                  filterOutIssues(webview.params.patchPath!).then(() => {

                    getOutputFromAnalyzerOfAFile();
                  });
                }
              });
            });
          }
        });
      }

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

      console.log(patched);

      // 3.
      applyPatchToFile(path.normalize(sourceFile), patched, patchFilepath);
      filterOutIssues(patchFilepath);

      // 4.
      vscode.commands.executeCommand("setContext", "patchApplyEnabled", false);
      getOutputFromAnalyzerOfAFile();

    }
    logging.LogInfo("===== Finished applyPatch command. =====");
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

      Object.keys(issues).forEach((key) => {
        let patchFolder = PATCH_FOLDER;

        issues[key].forEach((issue: any) => {
          issue.patches.forEach((patch: any) => {
            if (patch.path === patchPath || patchPath.includes(patch.path)) {
              issues[key].splice(issues[key].indexOf(issue), 1);
              if (!issues[key].length) {
                delete issues[key];
              }
            }
          });
        });
      });
      // if (!tree[key].patches.length) {
      //     delete tree[key];
      // }
    }
    let issuesStr = stringify(issues);
    console.log(issuesStr);

    let issuesPath: string | undefined = "";
    if (
      vscode.workspace
        .getConfiguration()
        .get<string>("aifix4seccode.analyzer.issuesPath")
    ) {
      issuesPath = vscode.workspace
        .getConfiguration()
        .get<string>("aifix4seccode.analyzer.issuesPath");
    }
    writeFileSync(issuesPath!, issuesStr, utf8Stream);
  }

  function saveFileAndFixesToState(filePath: string) {
    logging.LogInfo(filePath);

    let issuesPath: string | undefined = "";
    if (
      vscode.workspace
        .getConfiguration()
        .get<string>("aifix4seccode.analyzer.issuesPath")
    ) {
      issuesPath = vscode.workspace
        .getConfiguration()
        .get<string>("aifix4seccode.analyzer.issuesPath");
    }

    var originalFileContent = readFileSync(filePath!, "utf8");
    var originalIssuesContent = readFileSync(issuesPath!, "utf8");
    context.workspaceState.update(
      "lastFileContent",
      JSON.stringify(originalFileContent)
    );
    context.workspaceState.update("lastFilePath", JSON.stringify(filePath));

    context.workspaceState.update(
      "lastIssuesContent",
      JSON.stringify(originalIssuesContent)
    );
    context.workspaceState.update("lastIssuesPath", JSON.stringify(issuesPath));
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
      console.log(fixes);
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

    var outputFolder = vscode.workspace
      .getConfiguration()
      .get<string>("aifix4seccode.analyzer.generatedPatchesPath");
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
      console.log(err);
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
    var outputFolder = vscode.workspace
      .getConfiguration()
      .get<string>("aifix4seccode.analyzer.generatedPatchesPath");
    if (!outputFolder) {
      outputFolder = vscode.workspace.workspaceFolders![0].uri.path;
    }

    var patch = "";
    try {
      patch = readFileSync(outputFolder + "/" + patchPath, "utf8");
    } catch (err) {
      console.log(err);
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