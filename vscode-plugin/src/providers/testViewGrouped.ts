import * as vscode from "vscode";
import { IFix } from "../interfaces";
import * as path from "path";
import { getIssues, getIssues2 } from "../services/fakeAiFixCode";
import { writeFileSync } from "fs";
import { ISSUE, utf8Stream, ISSUES_PATH } from "../constants";
var stringify = require("json-stringify");

let tree: any;

export class GroupedTestView {
  public treeDataProvider: NodeWithIdTreeDataProvider | undefined;
  constructor(context: vscode.ExtensionContext) {
    initTree()
      .then(() => {
        this.treeDataProvider = new NodeWithIdTreeDataProvider();
        const view = vscode.window.createTreeView("groupedTestView", {
          treeDataProvider: this.treeDataProvider,
          showCollapseAll: true,
        });
        context.subscriptions.push(view);

        // Register commands without empty catch blocks
        try {
          vscode.commands.registerCommand("groupedTestView.reveal", async () => {
            const key = await vscode.window.showInputBox({
              placeHolder: "Type the label of the item to reveal",
            });
            if (key) {
              const item = this.treeDataProvider!.findTreeItem(key);
              if (item) {
                await view.reveal(item as any, {
                  focus: true,
                  select: false,
                  expand: true,
                });
              } else {
                vscode.window.showInformationMessage(`Item '${key}' not found.`);
              }
            }
          });
        } catch { }
        try {
          vscode.commands.registerCommand("groupedTestView.changeTitle", async () => {
            const title = await vscode.window.showInputBox({
              prompt: "Type the new title for the Grouped Test View",
              placeHolder: view.title,
            });
            if (title) {
              view.title = title;
            }
          });
        } catch { }
      })
      .catch((error) => {
        console.error('Error in constructor after initTree:', error);
      });
  }
}

async function initTree() {
  try {
    const issuesObject = await getIssues2();
    console.log('Issues from getIssues2:', issuesObject);

    // Flatten the issues object into a single array
    const issuesArrays = Object.values(issuesObject); // Get arrays of issues
    const flatIssues = Object.values(issuesObject).reduce((acc: any, issuesArray: any) => acc.concat(issuesArray), []);


    console.log('Flattened Issues:', flatIssues);

    tree = groupIssuesByFile(flatIssues as any);
    console.log('Grouped Tree:', tree);
  } catch (error) {
    console.error('Error in initTree:', error);
  }
}

function groupIssuesByFile(issues: any[]) {
  const groupedTree: any = {};

  issues.forEach((issue: any) => {
    // Use the logic from getTreeElement to extract the JavaFileName
    const fileName = getJavaFileNameFromTree(issue) || 'Unknown File';

    if (!groupedTree[fileName]) {
      groupedTree[fileName] = [];
    }
    groupedTree[fileName].push(issue);
  });

  return groupedTree;
}

function getJavaFileNameFromTree(issue: any): string {
  return issue["JavaFileName"] || 'Unknown File';
}

let nodes: string[] = [];
let counter = 1;

class NodeWithIdTreeDataProvider
  implements vscode.TreeDataProvider<{ key: string }> {
  private _onDidChangeTreeData: vscode.EventEmitter<
    { key: string } | undefined | null | void
  > = new vscode.EventEmitter<{ key: string } | undefined | null | void>();
  readonly onDidChangeTreeData: vscode.Event<
    { key: string } | undefined | null | void
  > = this._onDidChangeTreeData.event;

  refresh(patchPath: string): void {
    if (patchPath && patchPath !== "") {
      filterTree(patchPath);
    }
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element: { key: string }): vscode.TreeItem {
    const treeItem = getTreeItem(element.key);
    treeItem.id = (++counter).toString();
    return treeItem;
  }

  getChildren(element: { key: string }): { key: string }[] {
    let children = getChildren(element ? element.key : undefined!);
    let childrenNodes = children.map((key: any) => getNode(key));
    return childrenNodes;
  }

  getParent({ key }: { key: string }): { key: string } {
    const parentKey = key.includes('#') ? key.split('#')[0] : '';
    return (parentKey ? new Key(parentKey) : void 0)!;
  }

  // Add a method to find TreeItem by label (for reveal command)
  findTreeItem(label: string): vscode.TreeItem | undefined {
    // Search in top-level file nodes
    if (tree[label]) {
      return getTreeItem(label);
    }
    // Search in issues
    for (const fileName of Object.keys(tree)) {
      const issues = tree[fileName];
      for (let i = 0; i < issues.length; i++) {
        const issue = issues[i];
        const issueLabel = issue.name;
        if (issueLabel === label) {
          const key = fileName + '#' + i;
          return getTreeItem(key);
        }
      }
    }
    return undefined;
  }
}

function getChildren(key: string) {
  if (!key) {
    // Return top-level keys (file names)
    return Object.keys(tree);
  } else {
    // Return the issues under each file name
    return tree[key].map((issue: any, index: number) => key + '#' + index);
  }
}

function getTreeItem(key: string): vscode.TreeItem {
  const treeElement = getTreeElement(key);
  const tooltip = new vscode.MarkdownString(
    "$(zap) Click to show the source of ${key}",
    true
  );

  if (Array.isArray(treeElement)) {
    // It's a file node
    let itemLabel = "";
    let labelText = (treeElement.length > 1) ? key + ' (' + treeElement.length + ' issues)' : key + ' (' + treeElement.length + ' issue)';
    if (treeElement) {
      itemLabel = <any>{
        label: labelText,
        highlights:
          key.length > 1 ? [[key.length - 2, key.length - 1]] : void 0,
      };
    }
    return {
      label: itemLabel,
      tooltip,
      collapsibleState: vscode.TreeItemCollapsibleState.Collapsed,
      iconPath: {
        light: path.join(
          __filename,
          "..",
          "..",
          "..",
          "resources",
          "icons",
          "light",
          "eye.svg"
        ),
        dark: path.join(
          __filename,
          "..",
          "..",
          "..",
          "resources",
          "icons",
          "dark",
          "eye.svg"
        ),
      },
    };
  } else {
    // It's an issue node
    let itemLabel = "";
    if (treeElement) {
      itemLabel = <any>{
        label: treeElement.name || key,
        highlights:
          key.length > 1 ? [[key.length - 2, key.length - 1]] : void 0,
      };
    }

    let commandArguments: any;
    if (treeElement.patches && treeElement.patches.length > 0) {
      // When patches are available, pass the patch path
      commandArguments = [treeElement.patches[0].path];
    } else {
      // When patches are empty, pass the issue data
      commandArguments = [{
        sourceFile: treeElement.sourceFile,
        textRange: treeElement.textRange
      }];
    }

    return {
      label: itemLabel,
      tooltip,
      command: {
        title: "Open issue",
        command: "aifix4seccode-vscode.openUpFile",
        arguments: commandArguments,
      },
      collapsibleState: vscode.TreeItemCollapsibleState.None,
      iconPath: {
        light: path.join(
          __filename,
          "..",
          "..",
          "..",
          "resources",
          "icons",
          "light",
          "screwdriver.svg"
        ),
        dark: path.join(
          __filename,
          "..",
          "..",
          "..",
          "resources",
          "icons",
          "dark",
          "screwdriver.svg"
        ),
      },
    };
  }
}

function getTreeElement(element: any) {
  if (!isNaN(element)) {
    return undefined;
  }
  if (tree[element]) {
    // It's a file node
    return tree[element];
  } else {
    // It's an issue node
    let [fileName, indexStr] = element.split('#');
    let index = parseInt(indexStr);
    let issueItem = tree[fileName][index];

    // Add sourceFile information extracted from the issue data
    let sourceFileName = issueItem["JavaFileName"];

    return {
      ...issueItem,
      sourceFile: sourceFileName
    };
  }
}

function getNode(key: any): { key: string } {
  if (!nodes.includes(key)) {
    nodes.push(key);
  }
  return { key: nodes[nodes.indexOf(key)] };
}

function filterTree(patchPath: string) {
  Object.keys(tree).forEach((key) => {
    tree[key] = tree[key].filter((issue: any) => {
      issue.patches = issue.patches.filter((patch: any) => {
        return !(patch.path === patchPath || patchPath.includes(patch.path));
      });
      // Return true if issue still has patches or no patches at all
      return issue.patches.length > 0 || !issue.patches;
    });
    if (tree[key].length === 0) {
      delete tree[key];
    }
  });
  console.log(tree);
}

class Key {
  constructor(readonly key: string) { }
}