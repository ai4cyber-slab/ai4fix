import { ExecSyncOptionsWithStringEncoding } from 'child_process';
import { workspace } from 'vscode';
import { getRootPath } from './path';
import * as fs from 'fs';
import * as upath from 'upath';
import * as vscode from 'vscode';
import * as logging from "./services/logging";

var path = require("path");
var os = require('os');



// EXTENSION SETTINGS:
const dockerWorkdir = process.env.WORKDIR_PATH || '/app';
let configPath = upath.join(dockerWorkdir, 'config.properties');
const normalized_configPath = upath.normalize(configPath);

let config: { [section: string]: { [key: string]: string } } = {};

try {
  if (normalized_configPath && fs.existsSync(normalized_configPath)) {
    const configContent = fs.readFileSync(normalized_configPath, 'utf8');
    config = parseConfig(configContent);
  } else {
    vscode.window.showErrorMessage('Configuration file not found: ' + normalized_configPath);
  }
} catch (err) {
  logging.LogErrorAndShowErrorMessage('Error reading config file: ', err as any);
}

function parseConfig(content: string): { [section: string]: { [key: string]: string } } {
  const lines = content.split('\n');
  const result: { [section: string]: { [key: string]: string } } = {};
  let currentSection = 'DEFAULT';

  result[currentSection] = {};

  lines.forEach((line) => {
    const strippedLine = line.trim();

    if (!strippedLine || strippedLine.startsWith('#')) {
      return;
    }

    const cleanedLine = strippedLine.split('#', 1)[0].trim();

    if (cleanedLine.startsWith('[') && cleanedLine.endsWith(']')) {
      currentSection = cleanedLine.slice(1, -1).trim();
      if (!result[currentSection]) {
        result[currentSection] = {};
      }
      return;
    }

    if (cleanedLine.includes('=')) {
      const [key, value] = cleanedLine.split('=');

      if (key.trim() && value.trim()) {
        result[currentSection][key.trim()] = value.trim();
      }
    }
  });

  return result;
}

function insertHiddenFile(projectPath: string, originalPath: string): string {
  const HIDDEN = '.ai4framework';

  if(upath.isAbsolute(originalPath)) {
    originalPath = upath.relative(projectPath, originalPath);
  }

  const normalizedProjectPath = upath.normalize(projectPath);
  const normalizedPath = upath.normalize(originalPath);
  const adjustedPath = upath.join(normalizedProjectPath, HIDDEN, normalizedPath);

  return adjustedPath
}


export let PROJECT_FOLDER = upath.normalize(vscode.workspace.workspaceFolders![0].uri.fsPath);

export function SetProjectFolder(path: string) {
  PROJECT_FOLDER = upath.normalize(upath.toUnix(path));
  PROJECT_FOLDER_LOG = 'plugin.subject_project_path' + '=' + PROJECT_FOLDER + os.EOL;
}

// Access values from the parsed config
export const PATCH_FOLDER = insertHiddenFile(PROJECT_FOLDER, upath.normalize(config['DEFAULT']?.['config.results_path'] || 'patches'));
export const ISSUES_PATH = insertHiddenFile(PROJECT_FOLDER, upath.normalize(config['DEFAULT']?.['config.jsons_listfile'] || 'jsons.lists'))
export const ANALYZER_USE_DIFF_MODE = config['PLUGIN']?.['plugin.use_diff_mode'] || 'view Diffs';

let test_folder_path = config['PLUGIN']?.['plugin.test_folder_log'] || '';
if(!upath.isAbsolute(test_folder_path)) {
  test_folder_path = upath.resolve(PROJECT_FOLDER, test_folder_path);
}
export const TEST_FOLDER = test_folder_path;

export const SCRIPT_PATH = config['PLUGIN']?.['plugin.script_path'] || '/app';
export const ANALYZER_MENTION = 'analyzer_mention';
export const ISSUE = 'issue';


// lOGS:
export const LOG_HEADING = '# Vscode-Plugin settings' + os.EOL + os.EOL;
export const PATCH_FOLDER_LOG = 'plugin.generated_patches_path' + '=' + PATCH_FOLDER + os.EOL;
export const ISSUES_PATH_LOG = 'plugin.jsons_listfile' + '=' + ISSUES_PATH + os.EOL;
export var PROJECT_FOLDER_LOG = 'plugin.subject_project_path' + '=' + PROJECT_FOLDER + os.EOL;
export const ANALYZER_USE_DIFF_MODE_LOG = 'plugin.use_diff_mode' + '=' + ANALYZER_USE_DIFF_MODE + os.EOL;


export const UNSAVED_SYMBOL = ' •';
export const fileNotSupported = `The file is not displayed in the editor because it is either binary, uses an unsupported text encoding or it's an empty file`;
export const utf8Stream: ExecSyncOptionsWithStringEncoding = {
  encoding: 'utf8',
};
export const cwdCommandOptions = {
  ...utf8Stream,
  cwd: getRootPath(),
};
