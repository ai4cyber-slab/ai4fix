# AI4Framework User Guide

Welcome to **AI4Framework**! This guide will walk you through setting up and using the framework step by step.

---

## Table of Contents

1. [What is AI4Framework?](#what-is-ai4framework)
2. [Before You Start](#before-you-start)
3. [Setting Up AI4Framework](#setting-up-ai4framework)
4. [Running Docker](#running-docker)
    - [On Windows](#on-windows)
    - [On Linux or macOS](#on-linux-or-macos)
5. [Analyzing Your Project](#analyzing-your-project)
    - [Option 1: Using the Built-in Editor](#option-1-using-the-built-in-editor)
    - [Option 2: Using Command Line Access (Headless Mode)](#option-2-using-command-line-access-headless-mode)
    - [Configuration File](#configuration-file)
    - [Orchestrator.py Script Options](#orchestratorpy-script-options)
6. [Example Scenario: Running AI4Framework on macOS in Headless Mode](#example-scenario-running-ai4framework-on-macos-in-headless-mode)
    - [Reviewing and Retrieving the Results](#reviewing-and-retrieving-the-results)
7. [Need Support?](#need-support)

---

## What is AI4Framework?

**AI4Framework** is a tool that automatically checks your code for issues and suggests fixes, helping you improve your code's quality and security.

---

## Before You Start

### Prerequisites

- **Operating System**: Windows, Linux, or macOS
- **Docker**: Installed and running ([Download Docker](https://www.docker.com/get-started))
- **Git and Git LFS**: Installed ([Download Git](https://git-scm.com/downloads), [Download Git LFS](https://git-lfs.github.com/))
  - **Important**: AI4Framework's repository contains large files managed by Git LFS.
- **A Maven-Structured Project**: Your project should be organized with Maven (typically contains a `pom.xml` file in the root directory).
- **Configuration File**: A `config.properties` file in your project's root folder. See the guide in the [Configuration File](#configuration-file) section.

---

## Setting Up AI4Framework

### Step 1: Clone the AI4Framework Repository

Ensure Git LFS is installed and initialized:

```bash
git lfs install
```

Clone the repository:

```bash
git clone --branch dev --single-branch https://github.com/ai4cyber-slab/ai4fix.git
```

If Git LFS does not retrieve large files automatically, navigate to the `ai4framework` directory and run:

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

### Step 2: Navigate to the AI4Framework Directory

```bash
cd ai4framework
```

---

## Running Docker

### On Windows

#### Step 1: Open PowerShell

Press `Win + X` and select **Windows PowerShell**.

#### Step 2: Run the following command

Replace placeholders with your information:

```powershell
.\ai4framework_entry.ps1 -LOCAL_PROJECT_PATH "C:\path\to\your\project" -CONTAINER_PROJECT_PATH "/project" -PORT 8080
```

- **`C:\path\to\your\project`**: Full path to your project folder.
- **`/project`**: Path inside the container (usually `/project`).
- **`8080`**: Port number (change if needed).

### On Linux or macOS

#### Step 1: Open Terminal

#### Step 2: Run the following command

Replace placeholders with your information:

```bash
bash ai4framework_entry.sh --LOCAL_PROJECT_PATH "/path/to/your/project" --CONTAINER_PROJECT_PATH "/project" --PORT 8080
```

- **`/path/to/your/project`**: Full path to your project folder.
- **`/project`**: Path inside the container (usually `/project`).
- **`8080`**: Port number (change if needed).

---

## Analyzing Your Project

After running the above command, AI4Framework sets up a Docker container where your project will be analyzed.

You have two options to proceed:

### Option 1: Using the Built-in Editor

This method lets you use a web-based code editor similar to Visual Studio Code.

#### Step 1: Access the Web Editor

- After running Docker, look for a message like:

  ```
  Container is running with code-server support. Navigate to http://localhost:XXXX/?folder=/*
  ```

- Open your web browser and go to that address.

#### Step 2: Open the Terminal in the Editor

- In the web editor, click on **Terminal** > **New Terminal**.

#### Step 3: Run the Analysis

- In the terminal, type:

  ```bash
  python /app/orchestrator.py
  ```

- Press **Enter**.

### Option 2: Using Command Line Access (Headless Mode)

If you prefer using the command line without the web editor, run Docker with an additional argument to get direct access to the container's terminal.

#### Step 1: Run Docker with Bash Access

**On Windows:**

```powershell
.\ai4framework_entry.ps1 -LOCAL_PROJECT_PATH "C:\path\to\your\project" -CONTAINER_PROJECT_PATH "/project" -PORT 8080 -RunWithBash
```

**On Linux or macOS:**

```bash
bash ai4framework_entry.sh --LOCAL_PROJECT_PATH "/path/to/your/project" --CONTAINER_PROJECT_PATH "/project" --PORT 8080 --RunWithBash
```

#### Step 2: Run the Analysis Inside the Container

Once the container starts, you'll be in its command line interface.

- Type:

  ```bash
  python /app/orchestrator.py
  ```

- Press **Enter**.

---

### Configuration File

Create a `config.properties` file in your project's root folder with the following content:

```properties
[DEFAULT]
config.filter= # Words to filter files (if present in file paths, those files will be ignored). Leave empty to analyze all files.
config.rounds_count=1 # Number of times to run the process. Useful for auto patching with '--auto' option.

[API]
config.provider=openai # Service to use ('groq', 'openai', 'claude')
config.key=your_api_key # Enter your API key directly
config.model=gpt-4o # Desired model name
config.temperature=0 # Desired temperature

[SAST]
config.spotbugs_bin=/opt/spotbugs-4.8.6/bin/spotbugs # Path as specified in the Dockerfile
config.pmd_bin=/opt/pmd-bin-7.4.0/bin/pmd # Path as specified in the Dockerfile
config.pmd_ruleset=/app/utils/PMD-config.xml # Leave as default or change if needed

[ANALYZER]
config.analyzer=/opt/AI4VULN/Java/AnalyzerJava # Path as specified in the Dockerfile

[PLUGIN]
plugin.use_diff_mode=view Diffs # Do not change
plugin.script_path=/app # Do not change
plugin.test_folder_log=src/test # Path of the test folder in your project
```

---

### Orchestrator.py Script Options

You can customize the analysis by providing various command-line arguments.

#### Usage

```bash
python /app/orchestrator.py [options]
```

#### Options

- **`-h`, `--help`**: Show help message and exit.
- **`-c COMMIT_SHA`, `--commit_sha COMMIT_SHA`**: Analyze only files changed in the specified commit.
- **`--skip-patches`**: Perform analysis without generating patches.
- **`--sast-rerun`**: Run static analysis tools only.
- **`--auto`**: Automatically apply generated patches to your code.

#### Examples

- **Analyze the Entire Project**

  ```bash
  python /app/orchestrator.py
  ```

- **Analyze Files Changed in a Specific Commit**

  ```bash
  python /app/orchestrator.py -c <commit_sha>
  ```

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

---

## Example Scenario: Running AI4Framework on macOS in Headless Mode

Suppose you want to:

- Use **macOS**.
- Deploy AI4Framework in headless mode.
- Analyze the entire project folder.
- Use port **9090** because port 8080 is already in use.
- Obtain all **warnings and patches**.

### Steps

#### Step 1: Open Terminal

#### Step 2: Navigate to the AI4Framework Directory

```bash
cd ai4framework
```

#### Step 3: Prepare Your Project

Ensure your project is a **Maven-structured project**, in this case, located at `/path/to/your/project`.

#### Step 4: Create the `config.properties` File

In your project's root folder, create a file named `config.properties`. See the [Configuration File](#configuration-file) section for details.

#### Step 5: Run Docker with Bash Access and Custom Port

```bash
bash ai4framework_entry.sh --LOCAL_PROJECT_PATH "/path/to/your/project" --CONTAINER_PROJECT_PATH "/project" --PORT 9090 --RunWithBash
```

#### Step 6: Run the Analysis Inside the Container

```bash
python /app/orchestrator.py
```

### Reviewing and Retrieving the Results

After the analysis, AI4Framework creates a hidden `.ai4framework` folder in your project directory containing:

- **patches**: Validated `.diff` files with suggested fixes.
- **symbolic_results**: Issues found by the symbolic execution tool.
- **validation**: Details about issues found and suggested patches.
- **visualizations**: Statistics like the number of issues found/fixed, token consumption, etc.
- **issues.json**: A file listing all issues and suggested fixes.
- **sast_issues**: Issues found by static analysis tools.
- **jsons.lists**: Paths to the validated JSON files.

Back in your Mac terminal (outside the container), copy the results from the container to your local computer.
First, find the container ID by running:

```bash
docker ps -a
```

Note the container ID associated with AI4Framework.

Copy the `.ai4framework` folder from the container to your chosen directory:

```bash
docker cp <container_id>:/project/.ai4framework "/Users/username/path/to/chosen/directory"
```

Replace `<container_id>` with the actual container ID.

---

## Need Support?

If you have questions or need help:

- Visit the [GitHub repository](https://github.com/ai4cyber-slab/ai4fix) and check the issues section.
- Contact the maintainers through the repository.

---

Thank you for choosing **AI4Framework** to improve your code! We're here to help you make your projects better and more secure.