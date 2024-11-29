# AI4Framework User Guide

Welcome to **AI4Framework**! This guide will walk you through setting up and using the framework step by step.

---

## Table of Contents

1. [What is AI4Framework?](#what-is-ai4framework)
2. [Before You Start](#before-you-start)
3. [Setting Up AI4Framework](#setting-up-ai4framework)
4. [Running AI4Framework](#running-ai4framework)
   - [On Windows](#on-windows)
   - [On Linux or macOS](#on-linux-or-macos)
5. [Analyzing Your Project](#analyzing-your-project)
   - [Option 1: Using the Built-in Editor](#option-1-using-the-built-in-editor)
   - [Option 2: Using Command Line Access (Headless Mode)](#option-2-using-command-line-access-headless-mode)
   - [Understanding Orchestrator.py Script Options](#understanding-orchestratorpy-script-options)
6. [Example Scenario: Running AI4Framework on macOS in Headless Mode](#example-scenario-running-ai4framework-on-macos-in-headless-mode)
7. [Understanding the Results](#understanding-the-results)
8. [Getting Your Results Back](#getting-your-results-back)
9. [Additional Help](#additional-help)
10. [Need Support?](#need-support)

---

## What is AI4Framework?

**AI4Framework** is a tool that helps you automatically check your code for issues and even suggests fixes. Think of it as a smart assistant that reviews your code to make it better and more secure.

---

## Before You Start

### What You Need

1. **A Computer with One of the Following Operating Systems:**
   - Windows
   - Linux
   - macOS

2. **Docker Installed and Running:**
   - Docker allows applications to run in containers. If you don't have it, you can download it from [Docker's official site](https://www.docker.com/get-started).

3. **Git Installed:**
   - Git is a version control system. You can download it from [Git's official site](https://git-scm.com/downloads).

4. **Git LFS Installed:**
   - **Important**: AI4Framework's repository contains large files managed by Git LFS (Large File Storage). You need to install Git LFS to properly clone the repository.
   - Download Git LFS from [Git LFS's official site](https://git-lfs.github.com/).

5. **A Maven-Structured Project:**
   - AI4Framework works with projects organized using Maven. If you're not sure, Maven projects typically have a `pom.xml` file in the root directory.

6. **A Configuration File:**
   - You need to create a file named `config.properties` in the root folder of your project (the one you want to analyze). We'll guide you on how to do this in the [Additional Help](#additional-help) section.

---

## Setting Up AI4Framework

### Step 1: Install Git LFS

Before cloning the AI4Framework repository, you need to install Git LFS (Large File Storage) to handle large files in the repository.

#### Install Git LFS

- Download and install Git LFS from [Git LFS's official site](https://git-lfs.github.com/).
- Follow the installation instructions for your operating system.

#### Initialize Git LFS

- Open your command prompt (Windows) or terminal (Linux/macOS).
- Run the following command to initialize Git LFS:

  ```bash
  git lfs install
  ```

### Step 2: Download AI4Framework

Now, you're ready to clone the AI4Framework repository.

- In your command prompt or terminal, run:

  ```bash
  git clone --branch dev --single-branch https://github.com/ai4cyber-slab/ai4fix.git
  ```

This command downloads AI4Framework to your computer.

**Note**: Git LFS will automatically download the large files during the cloning process.

#### If Git LFS Does Not Retrieve Large Files

In some cases, Git LFS may not automatically download the large files. If you notice that some files are missing or appear as pointers (small text files), follow these steps:

- Navigate to the AI4Framework directory:

  ```bash
  cd ai4framework
  ```

- Run the following command to fetch the large files:

  ```bash
  git lfs pull
  ```

#### Manually Downloading Large Files

If you still cannot retrieve the large files using Git LFS, you can manually download them from GitHub:

1. Visit the [AI4Framework GitHub repository](https://github.com/ai4cyber-slab/ai4fix).

2. Navigate to the files or folders that are large (they might be indicated in the repository).

3. Download the files directly from GitHub by clicking on them and selecting **Download**.

4. Place the downloaded files into the appropriate directories within the `ai4framework` folder on your computer.

**Important**: Ensure that the files are placed in the correct locations to avoid any issues when running the framework.

### Step 3: Navigate to the AI4Framework Folder

- If you're not already in the AI4Framework directory, navigate there by running:

  ```bash
  cd ai4framework
  ```

Now you're inside the AI4Framework directory.

---

## Running AI4Framework

### On Windows

#### Step 1: Open PowerShell

- Press `Win + X` and select **Windows PowerShell**.

#### Step 2: Run the Script

Replace the placeholders with your information:

```powershell
.\ai4framework_entry.ps1 -LOCAL_PROJECT_PATH "C:\path\to\your\project" -CONTAINER_PROJECT_PATH "/project" -PORT 8080
```

- **`C:\path\to\your\project`**: The full path to your project folder.
- **`/project`**: The path inside the container (you can leave this as `/project`).
- **`8080`**: The port number (you can change this if needed).

### On Linux or macOS

#### Step 1: Open Terminal

#### Step 2: Run the Script

Replace the placeholders with your information:

```bash
bash ai4framework_entry.sh --LOCAL_PROJECT_PATH "/path/to/your/project" --CONTAINER_PROJECT_PATH "/project" --PORT 8080
```

- **`/path/to/your/project`**: The full path to your project folder.
- **`/project`**: The path inside the container (you can leave this as `/project`).
- **`8080`**: The port number (you can change this if needed).

---

## Analyzing Your Project

After running the script, AI4Framework sets up a special environment (a Docker container) where your project will be analyzed.

You have two options to proceed:

### Option 1: Using the Built-in Editor

This method lets you use a web-based code editor similar to Visual Studio Code.

#### Step 1: Access the Web Editor

- After running the script, look for a message like:

  ```
  Container is running with code-server support. Navigate to http://localhost:XXXX/?folder=/*
  ```

- Open your web browser and go to that address.

#### Step 2: Open the Terminal in the Editor

- In the web editor, click on **Terminal** in the top menu, then **New Terminal**.

#### Step 3: Run the Analysis

- In the terminal that opens at the bottom, type:

  ```bash
  python /app/orchestrator.py
  ```

- Press **Enter**.

The framework will initiate an analysis of your entire project. To view available options, use the `-h` argument.

### Option 2: Using Command Line Access (Headless Mode)

If you prefer using the command line without the web editor, you can run the script with an additional argument to get direct access to the container's terminal.

#### Step 1: Run the Script with Bash Access

**On Windows:**

```powershell
.\ai4framework_entry.ps1 -LOCAL_PROJECT_PATH "C:\path\to\your\project" -CONTAINER_PROJECT_PATH "/project" -PORT 8080 -RunWithBash
```

**On Linux or macOS:**

```bash
bash ai4framework_entry.sh --LOCAL_PROJECT_PATH "/path/to/your/project" --CONTAINER_PROJECT_PATH "/project" --PORT 8080 --RunWithBash
```

- The `-RunWithBash` or `--RunWithBash` argument tells the script to open the container with direct command line access after setup.

#### Step 2: Run the Analysis Inside the Container

Once the container starts, you'll be inside its command line interface.

- Type:

  ```bash
  python /app/orchestrator.py
  ```

- Press **Enter**.

The framework will start analyzing your entire project. To view available options, use the `-h` argument.

### Understanding Orchestrator.py Script Options

When running the `orchestrator.py` script, you can customize the analysis by providing various command-line arguments.

#### Usage

```bash
python /app/orchestrator.py [-h] [-r PROJECT_ROOT] [-c COMMIT_SHA] [--skip-patches] [--sast-rerun] [--auto]
```

**Description:**

Executes the security analysis workflow.

#### Optional Arguments

- **`-h`, `--help`**

  Show the help message and exit.

- **`-r PROJECT_ROOT`, `--project_root PROJECT_ROOT`**

  Path to the root directory of your project.

  - **Note**: If you have already provided the project path via the `ai4framework_entry.ps1` or `ai4framework_entry.sh` scripts using the `LOCAL_PROJECT_PATH` argument, you do not need to specify the `PROJECT_ROOT` again here.

- **`-c COMMIT_SHA`, `--commit_sha COMMIT_SHA`**

  The hash of the commit containing the modified files to be analyzed.

  - **Usage**: Use this argument if you want to analyze only the files changed in a specific commit rather than the entire project.
  - **Note**: If not provided, the whole project will be analyzed.

- **`--skip-patches`**

  If provided, the script will perform the analysis and generate warnings and results, but it will not generate any patches or `.diff` files for the issues found.

  - **Use Case**: Useful when you want to review the issues without generating suggested fixes.

- **`--sast-rerun`**

  If provided, the script will run the static analysis tools only, such as SpotBugs and PMD, without proceeding to the patch generation step.

  - **Use Case**: Useful when you want to update or refresh the static analysis results.

- **`--auto`**

  If provided, the script will automatically apply the generated patches to your code after the analysis is complete.

  - **How It Works**: After generating the `.diff` files (patches), the script will apply them one by one to your project files.
  - **Note**: This feature works based on the `config.rounds_count` setting in your `config.properties` file. If not all patches are applied successfully due to mismatches or conflicts, increasing `config.rounds_count` can allow the script to attempt multiple rounds of patch application.

#### Examples

- **Analyze the Entire Project**

  ```bash
  python /app/orchestrator.py
  ```

- **Analyze Only Files Changed in a Specific Commit**

  ```bash
  python /app/orchestrator.py -c <commit_sha>
  ```

  Replace `<commit_sha>` with the actual commit hash.

- **Analyze Without Generating Patches**

  ```bash
  python /app/orchestrator.py --skip-patches
  ```

- **Run Static Analysis Tools Only**

  ```bash
  python /app/orchestrator.py --sast-rerun
  ```

- **Automatically Apply Patches**

  ```bash
  python /app/orchestrator.py --auto
  ```

  - Ensure your `config.properties` file has the appropriate `config.rounds_count` setting. For example, setting `config.rounds_count=2` allows the script to attempt applying patches over two rounds.

#### Additional Notes

- **Combining Arguments**

  You can combine multiple arguments to customize the analysis. For example:

  ```bash
  python /app/orchestrator.py -c <commit_sha> --auto
  ```

  This command analyzes only the files changed in the specified commit and automatically applies the patches.

- **Project Root**

  If you need to specify a different project root within the container, use the `-r` or `--project_root` argument. However, in most cases, if you have set up the project path correctly when running the entry script, you don't need to specify this argument again.

- **Automatic Patch Application**

  The `--auto` flag works in conjunction with the `config.rounds_count` setting in your `config.properties` file. If some patches cannot be applied due to code changes or conflicts, increasing the `config.rounds_count` allows the script to attempt multiple times.

  - **Example `config.properties` Setting:**

    ```properties
    config.rounds_count=2
    ```

- **Limitations**

  - Automatic patch application might not always succeed if the code has significantly changed since the patches were generated.
  - Always review the applied patches to ensure they do not introduce new issues.

---

## Example Scenario: Running AI4Framework on macOS in Headless Mode

Let's walk through a specific example where:

- You're using **macOS**.
- You want to deploy AI4Framework in your infrastructure.
- You prefer to run it in **headless mode** (command line only).
- You want to analyze **the entire project folder**.
- You need to use port **9090** because port 8080 is already in use.
- You want to obtain all **warnings and patches** (`.diff` files).

### Step-by-Step Instructions

#### Step 1: Open Terminal

- On your Mac, open the **Terminal** application.

#### Step 2: Navigate to the AI4Framework Directory

- If you haven't already, clone the AI4Framework repository (with Git LFS):

  ```bash
  git clone --branch dev --single-branch https://github.com/ai4cyber-slab/ai4fix.git
  ```

  **Note**: Ensure Git LFS is installed and initialized before cloning.

- Change directory to AI4Framework:

  ```bash
  cd ai4framework
  ```

#### Step 3: Prepare Your Project

- Ensure your project is a **Maven-structured project**.
- Place your project folder somewhere accessible, e.g., `/Users/yourusername/projects/myproject`.

#### Step 4: Create the `config.properties` File

- In your project's root folder (`myproject`), create a file named `config.properties` with the following content:

  ```properties
  [DEFAULT]
  config.filter=test # A list of words that filters the files. If they are present in a file path, those files will be ignored. If nothing is passed, every file in the project will be analyzed.
  config.rounds_count=1 # Number of times to run the process. Default is 1. Useful for auto patching with python /app/orchestrator.py --auto
  [API]
  config.provider=openai # specify which service to use (groq, openai, claude)
  config.key=your_api_key  # Enter your API key directly without quotes
  config.model=gpt-4o # change to desired model name
  config.temperature=0 # change to desired temperature
  [SAST]
  config.spotbugs_bin=/opt/spotbugs-4.8.6/bin/spotbugs # change to where it's located
  config.pmd_bin=/opt/pmd-bin-7.4.0/bin/pmd # change to where it's located
  config.pmd_ruleset=/app/utils/PMD-config.xml # change to where it's located or leave the default
  [ANALYZER]
  config.analyzer=/opt/AI4VULN/Java/AnalyzerJava # change to where it's located
  # Vscode-Plugin settings
  [PLUGIN]
  plugin.use_diff_mode=view Diffs
  plugin.script_path=/app # makes the connection with the extension - do not change
  plugin.test_folder_log=src/test # path of the test folder in the directory to be analyzed - makes the connection with the extension
  ```

- **Note**: By leaving `config.filter` empty, all files in your project will be analyzed.

#### Step 5: Run the Script with Bash Access and Custom Port

- In the AI4Framework directory, run:

  ```bash
  bash ai4framework_entry.sh --LOCAL_PROJECT_PATH "/Users/yourusername/projects/myproject" --CONTAINER_PROJECT_PATH "/project" --PORT 9090 --RunWithBash
  ```

  - Ensure the `LOCAL_PROJECT_PATH` points to your project folder.
  - The `--PORT 9090` argument tells the script to use port **9090** instead of the default **8080**.
  - The `--RunWithBash` argument opens the container in headless mode.

#### Step 6: Run the Analysis Inside the Container

- Once inside the container's command line interface, start the analysis by typing:

  ```bash
  python /app/orchestrator.py
  ```

- Press **Enter**.

The framework will now analyze your entire project and generate warnings and patches.

#### Step 7: Wait for the Analysis to Complete

- The analysis might take some time, depending on the size of your project.
- You'll see progress messages in the terminal.

#### Step 8: Exit the Container

- After the analysis is complete, exit the container by typing:

  ```bash
  exit
  ```

- Press **Enter**.

#### Step 9: Retrieve the Results

- Back in your Mac terminal (outside the container), copy the results from the container to your local project folder.
- First, find the container ID by running:

  ```bash
  docker ps -a
  ```

- Note the container ID associated with AI4Framework.

- Copy the `.ai4framework` folder from the container to your project directory:

  ```bash
  docker cp <container_id>:/project/.ai4framework "/Users/yourusername/projects/myproject"
  ```

  - Replace `<container_id>` with the actual container ID.

#### Step 10: Review the Results

- Navigate to your project folder:

  ```bash
  cd "/Users/yourusername/projects/myproject"
  ```

- The `.ai4framework` folder contains all the warnings and patches (`.diff` files).

---

## Understanding the Results

Once the analysis is complete, AI4Framework creates a hidden folder in your project called `.ai4framework`. Here's what's inside:

- **patches**: Contains the validated `.diff` files with suggested fixes.
- **symbolic_results**: Issues found by the symbolic execution tool.
- **validation**: Relevant to the web-based editor option, this folder contains details about issues found and the suggested patches.
- **visualizations**: Stats like how many issues were found/fixed, token consumption, etc.
- **issues.json**: A file listing all the issues and suggested fixes.
- **sast_issues**: Issues found by static analysis tools.
- **jsons.lists**: Relevant to the web-based editor option, it holds paths to the validated JSON files.

---

## Getting Your Results Back

Before you finish, make sure to copy the results from the Docker container back to your computer.

### Step 1: Find Your Container ID

- Open a new terminal or command prompt (outside the container).
- Run:

  ```bash
  docker ps -a
  ```

- Note the container ID of the AI4Framework container (it may have a name similar to `ai4fix`).

### Step 2: Copy the Results

- Run:

  ```bash
  docker cp <container_id>:/project/.ai4framework /path/to/your/project
  ```

  Replace:

  - `<container_id>` with the ID of the Docker container running AI4Framework.
  - `/path/to/your/project` with the local path to your project folder on your computer.

Now, the `.ai4framework` folder with all the results is in your project folder.

---

## Additional Help

### Creating the `config.properties` File

In your project's root folder, create a file named `config.properties` with the following content:

```properties
[DEFAULT]
config.filter=test # A list of words that filters the files. If they are present in a file path, those files will be ignored. If nothing is passed, every file in the project will be analyzed.
config.rounds_count=1 # Number of times to run the process. Default is 1. Useful for auto patching with python /app/orchestrator.py --auto
[API]
config.provider=openai # specify which service to use (groq, openai, claude)
config.key=your_api_key  # Enter your API key directly without quotes
config.model=gpt-4o # change to desired model name
config.temperature=0 # change to desired temperature
[SAST]
config.spotbugs_bin=/opt/spotbugs-4.8.6/bin/spotbugs # as specified in the Dockerfile
config.pmd_bin=/opt/pmd-bin-7.4.0/bin/pmd # as specified in the Dockerfile
config.pmd_ruleset=/app/utils/PMD-config.xml # change to where it's located or leave the default
[ANALYZER]
config.analyzer=/opt/AI4VULN/Java/AnalyzerJava # path as specified in Dockerfile
# Vscode-Plugin settings
[PLUGIN]
plugin.use_diff_mode=view Diffs
plugin.script_path=/app # makes the connection with the extension - do not change
plugin.test_folder_log=src/test # path of the test folder in the directory to be analyzed - makes the connection with the extension
```

- **`config.filter`**: A list of words that filters the files. If they are present in a file path, those files will be ignored. If nothing is passed, every file in the project will be analyzed.
- **`config.rounds_count`**: Number of times to run the process. Default is 1. Useful for auto patching with `python /app/orchestrator.py --auto`.
- **`config.provider`**: Specify which service to use (`groq`, `openai`, `claude`).
- **`config.key`**: Enter your API key directly without quotes.
- **`config.model`**: Change to the desired model name.
- **`config.temperature`**: Change to the desired temperature.
- **`config.spotbugs_bin`**: Reference the Dockerfile for the saved location of SpotBugs.
- **`config.pmd_bin`**: Reference the Dockerfile for the saved location of PMD.
- **`config.pmd_ruleset`**: Change to where the PMD ruleset is located or leave the default.
- **`config.analyzer`**: Reference the Dockerfile for the saved location of the analyzer.
- **`plugin.use_diff_mode`**: Set to 'view Diffs' to use the diff mode.
- **`plugin.script_path`**: Makes the connection with the extension - do not change.
- **`plugin.test_folder_log`**: Path of the test folder in the directory to be analyzed - makes the connection with the extension.

### Entry Script Options and Help

You can view all available options for the entry script by running:

**On Windows:**

```powershell
.\ai4framework_entry.ps1 -h
```

**On Linux or macOS:**

```bash
bash ai4framework_entry.sh -h
```

**Entry Script Options:**

- **`LOCAL_PROJECT_PATH`**: Path to your local project directory.
- **`CONTAINER_PROJECT_PATH`**: Path inside the container where the project will reside.
- **`PORT`**: (Optional) Specify the port number for the container (default is `8080`).
- **`RunWithBash`**: (Optional) Open the container with command line access (Headless mode).

---

## Need Support?

If you have questions or need help:

- Visit the [GitHub repository](https://github.com/ai4cyber-slab/ai4fix) and check the issues section.
- Contact the maintainers through the repository.

---

Thank you for choosing **AI4Framework** to improve your code! We're here to help you make your projects better and more secure.