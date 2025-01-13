from .pmd import PMDRunner
from .spotbugs import SpotBugsRunner
from utils.logger import logger
import os
import time

class ToolRunner:
    """
    A class to manage and run various static analysis security testing (SAST) tools.

    This class provides methods to run PMD and SpotBugs on a given codebase,
    and handles the execution and logging of these tools.
    """

    def __init__(self, config, repo_manager, single_file=None):
        """
        Initialize the ToolRunner with configuration and repository manager.

        Args:
            config: Configuration object containing settings for the tools.
            repo_manager: RepoManager object to interact with the Git repository.
        """
        self.config = config
        self.filter = self.config.get('DEFAULT', 'config.filter', fallback='')
        self.project_root = self.config.get('DEFAULT', 'config.project_root')
        self.repo_manager = repo_manager
        self.pmd_runner = PMDRunner(config)
        self.spotbugs_runner = SpotBugsRunner(config)
        self.build_tool = self.config.get('DEFAULT', 'config.build_tool', fallback='maven')
        self.single_file = single_file

    def run_tool(self, tool_name, runner_method, files_to_analyze):
        """
        Run a specified SAST tool.

        Args:
            tool_name (str): Name of the tool being run.
            runner_method (callable): Method to run the tool.
            files_to_analyze (list): List of changed files to analyze.

        Logs the start and completion of the tool execution, and any errors encountered.
        """
        logger.info(f"Running {tool_name}...")
        start_time = time.time()
        try:
            runner_method(files_to_analyze)
            elapsed_time = time.time() - start_time
            logger.info(f"{tool_name} completed successfully in {elapsed_time:.2f} seconds.")
        except KeyboardInterrupt as k:
            logger.warning("program interrupted, shutting down...")
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Failed to run {tool_name} after {elapsed_time:.2f} seconds: {e}")

    def run_pmd(self):
        """
        Run PMD on Java files.

        Retrieves the list of Java files to be analyzed and runs PMD on them.
        """
        files_to_analyze = self.repo_manager.get_files_to_analyze(self.project_root, self.filter)
        if not files_to_analyze:
            logger.warning("PMD couldn't find any files to analyze.")
            return
        self.run_tool("PMD", self.pmd_runner.run, [self.single_file] if self.single_file else files_to_analyze)

    def run_spotbugs(self):
        """
        Run SpotBugs on Java class files.

        Finds the corresponding class files for Java files and runs SpotBugs on them.
        """
        files_to_analyze = self.find_class_changed_files(self.single_file)
        if not files_to_analyze:
            logger.warning("Spotbugs couldn't find any files to analyze.")
            return
        self.run_tool("SpotBugs", self.spotbugs_runner.run, files_to_analyze)

    def find_class_changed_files(self, single_file=None):
        """
        Find the corresponding .class files for the Java files.

        Returns:
            list: A list of paths to .class files corresponding to the Java files.
        """
        class_files = []
        files_list = [single_file] if single_file else self.repo_manager.get_files_to_analyze(self.project_root, self.filter)
        for java_file in files_list:
            class_file_path = find_class_file_from_java(java_file, self.build_tool)
            if class_file_path:
                class_files.append(class_file_path)
        return class_files if class_files else []

def find_class_file_from_java(java_file_path, build_tool):
    """
    Find the corresponding .class file for a given Java file, based on the build tool.

    Args:
        java_file_path (str): Path to the Java file.
        build_tool (str): The build tool being used ('maven' or 'gradle').

    Returns:
        str or None: Path to the corresponding .class file if found, None otherwise.
    """
    start_time = time.time()
    java_file = os.path.normpath(java_file_path)
    
    if build_tool.lower() == 'maven':
        if 'src' + os.path.sep + 'test' in java_file:
            class_path = java_file.replace(
                'src' + os.path.sep + 'test' + os.path.sep + 'java' + os.path.sep,
                'target' + os.path.sep + 'test-classes' + os.path.sep
            )
        elif 'src' + os.path.sep + 'main' in java_file:
            class_path = java_file.replace(
                'src' + os.path.sep + 'main' + os.path.sep + 'java' + os.path.sep,
                'target' + os.path.sep + 'classes' + os.path.sep
            )
        else:
            return None

    elif build_tool.lower() == 'gradle':
        if 'src' + os.path.sep + 'test' in java_file:
            class_path = java_file.replace(
                'src' + os.path.sep + 'test' + os.path.sep + 'java' + os.path.sep,
                'build' + os.path.sep + 'classes' + os.path.sep + 'java' + os.path.sep + 'test' + os.path.sep
            )
        elif 'src' + os.path.sep + 'main' in java_file:
            class_path = java_file.replace(
                'src' + os.path.sep + 'main' + os.path.sep + 'java' + os.path.sep,
                'build' + os.path.sep + 'classes' + os.path.sep + 'java' + os.path.sep + 'main' + os.path.sep
            )
        else:
            return None
    

    elif build_tool.lower() == 'javac':
        if 'src' + os.path.sep + 'main' in java_file:
            class_path = java_file.replace(
                'src' + os.path.sep + 'main' + os.path.sep + 'java' + os.path.sep,
                'build' + os.path.sep + 'classes' + os.path.sep + 'java' + os.path.sep + 'main' + os.path.sep
            )
        else:
            return None

    else:
        raise ValueError(f"Unsupported build tool: {build_tool}")
    class_path = class_path.replace('.java', '.class')
    elapsed_time = time.time() - start_time
    logger.debug(f"Time taken to search for class file: {elapsed_time:.2f} seconds")
    logger.debug(f"Class file path: {class_path}")
    return class_path