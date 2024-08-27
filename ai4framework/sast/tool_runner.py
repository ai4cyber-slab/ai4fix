from .pmd import PMDRunner
from .spotbugs import SpotBugsRunner
from .trivy import TrivyRunner
from utils.logger import logger
import os

class ToolRunner:
    def __init__(self, config, repo_manager):
        self.config = config
        self.repo_manager = repo_manager
        self.pmd_runner = PMDRunner(config)
        self.spotbugs_runner = SpotBugsRunner(config)
        self.trivy_runner = TrivyRunner(config)

    def run_tool(self, tool_name, runner_method, changed_files=None):
        logger.info(f"Running {tool_name}...")
        try:
            if changed_files is not None:
                runner_method(changed_files)
            else:
                runner_method()
            logger.info(f"{tool_name} completed successfully.")
        except Exception as e:
            logger.error(f"Failed to run {tool_name}: {e}")


    def run_pmd(self):
        changed_java_files = self.repo_manager.get_changed_files()
        self.run_tool("PMD", self.pmd_runner.run, changed_java_files)

    def run_spotbugs(self):
        class_changed_files = self.find_class_changed_files()
        self.run_tool("SpotBugs", self.spotbugs_runner.run, class_changed_files)

    def run_trivy(self):
        self.run_tool("Trivy", self.trivy_runner.run)

    def find_class_changed_files(self):
        project_root = self.repo_manager.repo.working_dir
        class_files = []

        for java_file in self.repo_manager.get_changed_files():
            if not java_file.endswith('.java'):
                logger.warning(f"Skipping non-Java file: {java_file}")
                continue

            class_file_path = find_class_file_from_java(java_file, project_root)
            if class_file_path:
                class_files.append(class_file_path)

        return class_files if class_files else []



def find_class_file_from_java(java_file_path, project_root):
    path_parts = java_file_path.strip(os.path.sep).split(os.path.sep)
    submodule_directory = path_parts[0] if not path_parts[0].startswith("src") else ""

    if 'src/main/java' in java_file_path:
        relative_class_path = java_file_path.split('src/main/java/', 1)[1]
        output_dir = 'target/classes'
    elif 'src/test/java' in java_file_path:
        relative_class_path = java_file_path.split('src/test/java/', 1)[1]
        output_dir = 'target/test-classes'
    else:
        logger.debug(f"Invalid path: {java_file_path}")
        return None

    relative_class_path = os.path.splitext(relative_class_path)[0] + '.class'
    class_file_path = os.path.join(project_root, submodule_directory, output_dir, relative_class_path)
    logger.debug(f"Looking for .class file at: {class_file_path}")

    if os.path.isfile(class_file_path):
        logger.debug(f"Class file found for: {java_file_path}")
        return class_file_path
    else:
        logger.debug(f"Class file not found for: {java_file_path}")
        return None