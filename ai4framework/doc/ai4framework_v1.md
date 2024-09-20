# AI4Framework Guide

## Introduction

AI4Framework is designed to enhance software development processes through the power of artificial intelligence. This framework combines various tools and technologies to provide comprehensive code analysis, vulnerability detection, and automated bug fixing capabilities. By leveraging static code analysis, symbolic execution, and so much more, AI4Framework aims to improve code quality, identify potential security risks, and streamline the development workflow.

![AI4Framework Workflow Diagram](workflow.png)

Key features of AI4Framework include:
- Automated code analysis using multiple static analysis tools
- Vulnerability scanning for both code and dependencies
- Symbolic execution for deep code inspection
- Integration with many models such as OpenAI's GPT models for intelligent code understanding and suggestion generation
- Customizable configuration to fit various project requirements

This guide provides detailed instructions on downloading necessary tools and configuring the `config.properties` file. Follow each step carefully to ensure a smooth setup and maximize the benefits of AI4Framework in your development process.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Git](#1-git)
3. [Python and Python Libraries](#2-python-and-python-libraries)
4. [OpenAI API Key](#3-openai-api-key)
5. [Maven](#4-maven)
6. [Static Tools: PMD](#5-static-tools-pmd)
7. [Static Tools: SpotBugs](#6-static-tools-spotbugs)
8. [Vulnerability Scanner: Trivy](#7-vulnerability-scanner-trivy)
9. [Java Development Kit (JDK)](#8-java-development-kit-jdk)
10. [Symbolic Execution Tool: RTEHunter](#9-symbolic-execution-tool-rtehunter)
11. [Final Notes](#final-notes)
12. [Building and Running AI4Framework with Code-Server using Docker](#building-and-running-ai4framework-with-code-server-using-docker)

---

## Prerequisites

Ensure your system meets the following requirements before proceeding:

- **Operating System**: Windows, Linux
- **Administrative Privileges**: Required for installing software and setting environment variables

---

## 1. Git

**Git** is a distributed version control system essential for managing your project's source code.

### Download

- **Git for Windows**: [Link](https://git-scm.com/download/win)
- **Git for Linux**: Typically available via package managers (e.g., `apt`, `brew`)

---

## 2. Python and Python Libraries

Python is required to run various components of the AI4Framework.

### Download

- **Python 3.9 or Later**: [Link](https://www.python.org/downloads/)

---

### 2.1. Install Python Libraries

Install libraries using `requirements.txt` file that will be provided within your project directory.

### Usage

- `pip install -r requirements.txt`

---

## 3. OpenAI API Key

At the moment, AI4Framework utilizes OpenAI's GPT models, requiring an API key for access, but more models will be added soon.

### Access

- **OpenAI Sign Up**: [Link](https://platform.openai.com/signup)

### Configuration

Add your OpenAI API key as an environment variable. Update your `.env` file or system environment variables accordingly.
```properties
OPENAI_API_KEY='your_api_key_here'
```

---

## 4. Maven

**Maven** is a build automation tool primarily used for Java projects.

### Download

- **Apache Maven**: [Link](https://maven.apache.org/download.cgi)


---

## 5. Static Tools: PMD

**PMD** is a static code analysis tool for identifying potential issues in Java code.

### Download

- **PMD 7.4.0**: [Link](https://github.com/pmd/pmd/releases)

### Configuration in `config.properties`

Set the PMD binary and ruleset paths:

```properties
config.pmd_bin=/path/to/pmd/bin/pmd
config.pmd_ruleset=/path/to/your/ruleset.xml
```

---

## 6. Static Tools: SpotBugs

**SpotBugs** is a static analysis tool for Java that detects bugs in your code.

### Download

- **SpotBugs 4.8.6**: [Link](https://github.com/spotbugs/spotbugs/releases)

### Configuration in `config.properties`

Set the SpotBugs binary path:

```properties
config.spotbugs_bin=/path/to/spotbugs/bin/spotbugs
```

---

## 7. Vulnerability Scanner: Trivy

**Trivy** is a comprehensive vulnerability scanner for containers and artifacts.

### Download

- **Trivy 0.54.1**: [Link](https://github.com/aquasecurity/trivy/releases)

### Configuration in `config.properties`

Set the Trivy binary path:

```properties
config.trivy_bin=/path/to/trivy
```

---

## 8. Java Development Kit (JDK)

The **Java Development Kit (JDK)** is essential for compiling and running Java applications within the AI4Framework.

### Download

- **JDK 11**: [Link](https://www.oracle.com/java/technologies/javase/jdk11-archive-downloads.html)


---

## 9. Symbolic Execution Tool: RTEHunter

**RTEHunter** is a symbolic execution tool that enhances the AI4Framework's ability to detect vulnerabilities.

### Download

- **RTEHunter Binary**: [Link to be added Later](https://github.com/AI4VULN/RTEHunter/releases)

### Configuration in `config.properties`

Set the analyzer paths and results path:

```properties
config.analyzer=/path/to/AI4VULN-analyzer
config.analyzer_path=/path/to/AI4VULN
config.analyzer_results_path=/path/to/results/
```

---

## `config.properties` Example

Below is a sample `config.properties` file. Update the paths according to your system setup.

```properties
[DEFAULT]
# General settings
config.project_name=your_project_name
config.project_path=/path/to/your/project
config.results_path=/path/to/your/project/patches
config.project_exec_path=/path/to/your/project/target
config.base_dir=/path/to/your/base/directory
config.project_build_tool=mavenCLI
config.project_source_path=src/main/java
config.jsons_listfile=/path/to/your/project/jsons.lists
config.prioritizer_path=/path/to/your/sorter/sorter.py
config.prioritizer_mode=glove

# Analyzer SAST tools
config.spotbugs_bin=/path/to/spotbugs/bin/spotbugs
config.spotbugs_output_file=/path/to/your/logs/jsons.list
config.pmd_bin=/path/to/pmd/bin/pmd
config.pmd_ruleset=/path/to/your/PMD-config.xml
config.trivy_bin=/path/to/trivy

config.jan_path=/path/to/your/JAN/Tools
config.jan_edition=JAN.jar
config.jan_compiler=jdk.compiler.jar
config.additional_tools_path=/path/to/your/additional/tools
config.jan2changepath_edition=JAN2ChangePath

config.validation_results_path=/path/to/your/project/patches/validation
config.archive_enabled=false
config.archive_path=/path/to/your/archive

# Vscode-Plugin settings
plugin.generated_patches_path=/path/to/your/project/patches
plugin.issues_path=/path/to/your/project/issues.lists
plugin.subject_project_path=/path/to/your/project
plugin.use_diff_mode=view Diffs

# Classifier specific arguments
[CLASSIFIER]
commit_sha=your_commit_sha_here
gpt_model=gpt-4
temperature=0

[ISSUES]
config.sast_issues_path=/path/to/your/sast_issues.json

# Reports paths
[REPORT]
config.pmd_report_path=/path/to/your/pmd.xml
config.spotbugs_report_path=/path/to/your/spotbugs.xml
config.trivy_report_path=/path/to/your/trivy.json

# FEA: SYMBOLIC EXECUTION
[ANALYZER]
config.analyzer=/path/to/your/AnalyzerJava
config.analyzer_path=/path/to/your/AI4VULN
config.analyzer_results_path=/path/to/your/project/results
```

---

## Final Notes

### Additional Dependencies

- **Python Dependencies**:
  - Always check the `requirements.txt` or `setup.py` file in the project for any additional Python dependencies.
  - Install them using:
    ```bash
    pip install -r requirements.txt
    ```

- **Java Dependencies**:
  - Maven will automatically handle Java dependencies as long as the `pom.xml` file is correctly configured.
  - To update dependencies, run:
    ```bash
    mvn clean install
    ```

### Security Best Practices

- **Environment Variables**:
  - Ensure that sensitive information, such as OpenAI API keys, is securely stored and not exposed in version control.
  - Use `.env` files or secure environment variable management systems.

- **Code Analysis Tools**:
  - Regularly run PMD, SpotBugs, and Trivy to identify and mitigate potential vulnerabilities in your codebase.

### Troubleshooting

- **Common Issues**:
  - **Path Not Found Errors**:
    - Ensure all environment variables are correctly set.
    - Verify the paths in `config.properties` point to the correct executable locations.
  
  - **Dependency Conflicts**:
    - Use virtual environments for Python to isolate dependencies.
    - Ensure Maven is correctly managing Java dependencies.

- **Getting Help**:
  - Contact us at ...

### Updating the Framework

- Regularly pull the latest changes from the repository to stay updated with new features and fixes:
  ```bash
  git pull origin main
  ```

- Update Python and Java dependencies as needed:
  ```bash
  pip install --upgrade -r requirements.txt
  mvn clean install
  ```

---


Here's the detailed guide for building the AI4Framework Docker image with code-server, and instructions for running the container:

---

## Building and Running AI4Framework with Code-Server using Docker

Follow the steps below to set up AI4Framework in a Docker container with code-server. This will allow you to perform code analysis and vulnerability scanning, along with using tools like PMD, SpotBugs, and Trivy, and potentially OpenAI's GPT models for classification.

### Step 1: Clone the Repository

First, clone the AI4Framework repository from your preferred Git hosting service (e.g., GitHub, GitLab):

```bash
git clone --branch dev https://github.com/ai4cyber-slab/ai4fix.git
```

### Step 2: Navigate to the AI4Framework Directory

Once the repository is cloned, navigate to the `ai4framework` directory:

```bash
cd ai4framework
```

### Step 3: Build the Docker Image

To build the Docker image that includes code-server and all necessary tools, use the following command. You can name the image as desired (in this example, we use `code-analyzer-vs-version`):

```bash
docker build -t code-analyzer-vs-version .
```

Make sure to replace `code-analyzer-vs-version` with your desired image name if needed.

### Step 4: Run the Docker Container

Once the Docker image is built, you can create and run the container. If you don't provide the `OPENAI_API_KEY`, the classification part will be skipped when running the Python script later.

Here's the command to run the container:

```bash
docker run -it -p 8080:8080 -e OPENAI_API_KEY='' -e PROJECT_PATH=/user_project -v C:/Users/HP/Music/pelo-project:/user_project code-analyzer-vs-version
```

#### Key Flags:
- `-p 8080:8080`: Exposes port 8080 for code-server access via a browser.
- `-e OPENAI_API_KEY=''`: You can leave this blank if you don't want to provide an OpenAI API key, or provide it if necessary.
- `-v C:/Users/HP/Music/pelo-project:/user_project`: Mounts the local project directory to the `/user_project` directory inside the container.
- `-e PROJECT_PATH=/user_project` project directory within the container.

If you do not provide the OpenAI API key, the classification using GPT models will be skipped.

#### Important:
 You can name the directory inside the container (`/user_project`) however you want, but ensure you consistently use the same name throughout your workflow. This directory will hold your local project ( eg: `C:/Users/HP/Music/pelo-project:/user_project`) inside the Docker container.

### Step 5: Access Code-Server

Once the container is running, open your web browser and go to the following URL to access code-server:

```
http://localhost:8080/?folder=/user_project
```

Make sure to replace `/user_project` with the correct project path inside the container if different.

### Step 6: Creating config.properties for the Project

Before running the Python script in VS Code for the project you want to analyze, you must create a config.properties file inside the project directory with the following content:
```
[DEFAULT]
# General project settings
config.project_name=user_project  # Change to your project name in container
config.project_path=/user_project  # Change to your project path in container

config.base_dir=/user_project  # Change to your project path in container
config.project_source_path=src/main/java  # Don't change this

# Static analysis tools paths
config.spotbugs_bin=/opt/spotbugs-4.8.6/bin/spotbugs  # Don't change this
config.pmd_bin=/opt/pmd-bin-7.4.0/bin/pmd  # Don't change this
config.pmd_ruleset=/app/utils/PMD-config.xml  # Can be changed to another ruleset if needed, otherwise use it's the dafault

config.trivy_bin=/usr/bin/trivy  # Don't change this

[CLASSIFIER]
# GPT model and classification settings
commit_sha=2f7bb20317500db89c1bc2c0d96275e09f3c62a1  # Change to the commit SHA you want to analyze
gpt_model=gpt-4  # Pick the GPT model to use (default is gpt-4)
temperature=0  # Set the temperature for GPT (default is 0)

[ISSUES]
# Path for SAST issues
config.sast_issues_path=/user_project/sast_issues.json  # Change '/user_project' to your project path in container

[REPORT]
# Report output paths (these can be customized)
config.pmd_report_path=/app/sast/out/pmd.xml  # Can be changed if needed
config.spotbugs_report_path=/app/sast/out/spotbugs.xml  # Can be changed if needed
config.trivy_report_path=/app/sast/out/trivy.json  # Can be changed if needed

[ANALYZER]
# Analyzer tool paths (these should not be changed)
config.analyzer=/opt/AI4VULN/Java/AnalyzerJava  # Don't change this
config.analyzer_path=/opt/AI4VULN  # Don't change this
config.analyzer_results_path=/user_project/results  # Change '/user_project' to your project path in container
```


### Step 7: Run the Python Script

Now, open the VSCode terminal in code-server and run the Python script for analysis. If you've already provided the project path as an environment variable (`PROJECT_PATH`), you can skip providing the path explicitly.

If you **did not** provide the project path as an environment variable, use this command:

```bash
python /app/orchestrator.py /user_project
```

If you **did** set the `PROJECT_PATH` environment variable earlier, you can simply run:

```bash
python /app/orchestrator.py
```

This will start the analysis process on your project.

---

By following these steps, you will be able to build and run the AI4Framework with code-server inside a Docker container, and conduct code analysis directly through the VSCode interface.