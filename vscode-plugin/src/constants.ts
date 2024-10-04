import { ExecSyncOptionsWithStringEncoding } from 'child_process';
import { workspace } from 'vscode';
import { getRootPath } from './path';
import * as fs from 'fs';
import * as upath from 'upath';
import * as vscode from 'vscode';

var path = require("path");
var os = require('os');



// EXTENSION SETTINGS:

const configPath = upath.normalize(vscode.workspace.getConfiguration().get<string>('aifix4seccode.analyzer.configPath') || '');

let config: { [section: string]: { [key: string]: string } } = {};

try {
  if (configPath && fs.existsSync(configPath)) {
    const configContent = fs.readFileSync(configPath, 'utf8');
    config = parseConfig(configContent);
  } else {
    vscode.window.showErrorMessage('Configuration file not found: ' + configPath);
  }
} catch (err) {
  vscode.window.showErrorMessage('Error reading config file: ' + err);
}

function parseConfig(content: string): { [section: string]: { [key: string]: string } } {
  const lines = content.split('\n');
  const result: { [section: string]: { [key: string]: string } } = {};
  let currentSection = 'DEFAULT';

  lines.forEach((line) => {
    line = line.trim();

    if (line.startsWith('#') || line === '') return;

    if (line.startsWith('[') && line.endsWith(']')) {
      currentSection = line.slice(1, -1);
      result[currentSection] = {};
    } else if (line.includes('=') && !line.startsWith('#')) {
      const [key, value] = line.split('=');
      if (key && value) {
        result[currentSection][key.trim()] = value.trim();
      }
    }
  });

  return result;
}

export var PROJECT_FOLDER = upath.normalize(config['DEFAULT']?.['config.project_path'] || '');

export function SetProjectFolder(path: string) {
  PROJECT_FOLDER = upath.normalize(path);
  PROJECT_FOLDER_LOG = 'plugin.subject_project_path' + '=' + PROJECT_FOLDER + os.EOL;
}

// Access values from the parsed config
export const PATCH_FOLDER = upath.normalize(config['DEFAULT']?.['config.results_path'] || '');
export const ISSUES_PATH = upath.normalize(config['DEFAULT']?.['config.jsons_listfile'] || '');
export const ANALYZER_USE_DIFF_MODE = config['PLUGIN']?.['plugin.use_diff_mode'] || '';
export const TEST_FOLDER = config['PLUGIN']?.['plugin.test_folder_log'] || '';
export const SCRIPT_PATH = config['PLUGIN']?.['plugin.script_path'] || '';
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
