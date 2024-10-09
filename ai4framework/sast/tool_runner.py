from .pmd import PMDRunner
from .spotbugs import SpotBugsRunner
from .trivy import TrivyRunner
from utils.logger import logger
import os
import time

class ToolRunner:
    """
    A class to manage and run various static analysis security testing (SAST) tools.

    This class provides methods to run PMD, SpotBugs, and Trivy on a given codebase,
    and handles the execution and logging of these tools.
    """

    def __init__(self, config, repo_manager):
        """
        Initialize the ToolRunner with configuration and repository manager.

        Args:
            config: Configuration object containing settings for the tools.
            repo_manager: RepoManager object to interact with the Git repository.
        """
        self.config = config
        self.repo_manager = repo_manager
        self.pmd_runner = PMDRunner(config)
        self.spotbugs_runner = SpotBugsRunner(config)
        self.trivy_runner = TrivyRunner(config)

    def run_tool(self, tool_name, runner_method, changed_files=None):
        """
        Run a specified SAST tool.

        Args:
            tool_name (str): Name of the tool being run.
            runner_method (callable): Method to run the tool.
            changed_files (list, optional): List of changed files to analyze.

        Logs the start and completion of the tool execution, and any errors encountered.
        """
        logger.info(f"Running {tool_name}...")
        start_time = time.time()
        try:
            if changed_files is not None:
                runner_method(changed_files)
            else:
                runner_method()
            elapsed_time = time.time() - start_time
            logger.info(f"{tool_name} completed successfully in {elapsed_time:.2f} seconds.")
        except KeyboardInterrupt as k:
            logger.warning("program interrupted, shutting down...")
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Failed to run {tool_name} after {elapsed_time:.2f} seconds: {e}")

    def run_pmd(self):
        """
        Run PMD on changed Java files.

        Retrieves the list of changed Java files and runs PMD on them.
        """
        changed_java_files = self.repo_manager.get_changed_files()
        self.run_tool("PMD", self.pmd_runner.run, changed_java_files)

    def run_spotbugs(self):
        """
        Run SpotBugs on changed class files.

        Finds the corresponding class files for changed Java files and runs SpotBugs on them.
        """
        class_changed_files = self.find_class_changed_files()
        self.run_tool("SpotBugs", self.spotbugs_runner.run, class_changed_files)

    def run_trivy(self):
        """
        Run Trivy on the project.

        Executes Trivy without specifying changed files, as it typically scans the entire project.
        """
        self.run_tool("Trivy", self.trivy_runner.run)

    def find_class_changed_files(self):
        """
        Find the corresponding .class files for changed Java files.

        Returns:
            list: A list of paths to .class files corresponding to changed Java files.
        """
        start_time = time.time()
        # project_root = self.repo_manager.repo.working_dir
        class_files = []

        for java_file in self.repo_manager.get_changed_files():
            if not java_file.endswith('.java'):
                logger.warning(f"Skipping non-Java file: {java_file}")
                continue

            class_file_path = find_class_file_from_java(java_file)
            if class_file_path:
                class_files.append(class_file_path)

        elapsed_time = time.time() - start_time
        logger.debug(f"Time taken to find changed class files: {elapsed_time:.2f} seconds")
        return class_files if class_files else []

def find_class_file_from_java(java_file_path):
    """
    Find the corresponding .class file for a given Java file.

    Args:
        java_file_path (str): Path to the Java file.
        project_root (str): Root directory of the project.

    Returns:
        str or None: Path to the corresponding .class file if found, None otherwise.
    """
    start_time = time.time()
    java_file = os.path.normpath(java_file_path)
    
    # Determine if it's a test file or main file
    if os.path.sep + 'src' + os.path.sep + 'test' + os.path.sep in java_file:
        # Test class files are usually in target/test-classes
        class_path = java_file.replace(os.path.sep + 'src' + os.path.sep + 'test' + os.path.sep + 'java' + os.path.sep, os.path.sep + 'target' + os.path.sep + 'test-classes' + os.path.sep)
    elif os.path.sep + 'src' + os.path.sep + 'main' + os.path.sep in java_file:
        # Main class files are usually in target/classes
        class_path = java_file.replace(os.path.sep + 'src' + os.path.sep + 'main' + os.path.sep + 'java' + os.path.sep, os.path.sep + 'target' + os.path.sep + 'classes' + os.path.sep)
    else:
        # If it's neither a test file nor a main file, return None
        return None
    
    # Replace .java with .class
    class_path = class_path.replace('.java', '.class')
    elapsed_time = time.time() - start_time
    logger.debug(f"Time taken to search for class file: {elapsed_time:.2f} seconds")
    return class_path