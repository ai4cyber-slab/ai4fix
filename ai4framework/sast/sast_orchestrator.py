import sys
import subprocess
import os
from pathlib import Path
import re

from utils.logger import logger
from .tool_runner import ToolRunner
from .report_merger import ReportMerger
from management.repo_manager import RepoManager
from utils.switcher import switch_java_version


class SASTOrchestrator:
    """
    Orchestrates the execution of Static Application Security Testing (SAST) tools.

    This class manages the overall process of running various SAST tools,
    including checking out specific commits, running the tools, and merging reports.
    """
    def __init__(self, config, single_file=None):
        """
        Initialize the SASTOrchestrator with configuration settings.

        Args:
            config: Configuration object containing necessary settings.
        """
        self.repo_manager = RepoManager(
            config.get('DEFAULT', 'config.project_root'),
            config.get('DEFAULT', 'config.commit_sha')
        )
        self.tool_runner = ToolRunner(config, self.repo_manager, single_file=single_file)
        self.report_merger = ReportMerger(config)
        self.project_path = config.get('DEFAULT', 'config.project_root')
        self.build_tool = config.get('DEFAULT', 'config.build_tool').lower()
        self.jdk_compiler_version = config.get('DEFAULT', 'config.jdk_compiler_version')
        self.build_mode= config.get('DEFAULT', 'config.build_mode').lower()

    def run_all(self, validation=False, tool=None, is_initial_round=True):
        """
        Run all configured SAST tools or specific ones based on the provided tool argument.

        This method orchestrates the SAST process, including:
        - Checking out the specified commit (if provided)
        - Running the specified tools (PMD, SpotBugs)
        - Merging reports from all tools
        
        Args:
            validation (bool): If True, perform validation steps in all methods. Default is False.
            tool (str): Specify the tool to run ("PMD" for PMD, "SB" for SpotBugs, or None for all). Default is None.
        """
        try:
            if not validation and self.repo_manager.commit_hash != '' and is_initial_round:
                self.repo_manager.checkout_commit()

            if tool is None or tool.upper() == "PMD":
                self.tool_runner.run_pmd()

            if not validation and (tool is None or tool.upper() == "SB"):
                self.run_compile(self.build_tool, validation=validation)

            if tool is None or tool.upper() == "SB":
                self.tool_runner.run_spotbugs()
                
            logger.info("SAST run completed")
            return self.report_merger.merge_reports(
                self.tool_runner.pmd_runner if tool is None or tool.upper() == "PMD" else None,
                self.tool_runner.spotbugs_runner if tool is None or tool.upper() == "SB" else None,
                validation=validation
            )
        except Exception as e:
            logger.error("An error occurred while running SAST tools: %s", e)
        finally:
            pass

    def run_compile(self, build_tool, validation=False):
        """
        Run the compile task using the specified build tool (Maven or Gradle).

        Args:
            build_tool (str): The build tool to use ('maven' or 'gradle').
            validation (bool): If True, suppress output during the build.

        Raises:
            ValueError: If an unsupported build tool is provided.
        """
        try:
            try:
                # First run clean online to fetch maven-clean-plugin
                clean_command = ['mvn', 'clean']
                subprocess.run(clean_command, cwd=self.project_path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
            switch_java_version(self.jdk_compiler_version)
            logger.info(f"{build_tool.capitalize()} compile started...")
            if build_tool.lower() == 'maven':
                # Then run the actual compile command
                command = ['mvn', 'compile', '-X', '-DskipTests']
                if self.build_mode == 'offline':
                    command.insert(1, '-o')
                if is_parallel_build_supported('maven'):
                    command.extend(['-T', str(os.cpu_count())])

            elif build_tool.lower() == 'gradle':
                command = ['gradle', '--no-daemon']
                if self.build_mode == 'offline':
                    command.append('--offline')
                if is_parallel_build_supported('gradle'):
                    command.extend([f'-Dorg.gradle.workers.max={os.cpu_count()}', '--parallel'])
                command.append('classes')
            
            elif build_tool.lower() == 'javac':
                build_dir = os.path.join('build', 'classes', 'java', 'main')
                os.makedirs(build_dir, exist_ok=True)
                java_files = [str(file) for file in Path('src/main/java').rglob('*.java')]
                if java_files:
                    command = ['javac', '-d', build_dir] + java_files
                else:
                    raise FileNotFoundError(f"Java files to analyze not found under folder src/main/java")
            else:
                raise ValueError(f"Unsupported build tool: {build_tool}")

            with subprocess.Popen(
                command,
                cwd=self.project_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            ) as process:
                for line in process.stdout:
                    if not validation:
                        print(line.strip())
                        logger.debug(line.strip())
                process.wait()

            if process.returncode == 0:
                logger.info(f"{build_tool.capitalize()} compile successful")
            else:
                logger.error(f"{build_tool.capitalize()} compile failed with return code {process.returncode}")
                sys.exit(process.returncode)

        except Exception as e:
            logger.error(f"An error occurred during {build_tool.capitalize()} compile: {str(e)}")
            sys.exit(1)
        finally:
            switch_java_version('11')







##################
# Helper functions
##################

def is_parallel_build_supported(build_tool):
    if build_tool == 'gradle':
        ex = 'gradle'
    elif build_tool == 'maven':
        ex = 'mvn'
    result = subprocess.run([ex, '-v'], capture_output=True, text=True)
    if result.returncode == 0:
        if build_tool == 'maven':
            version_match = re.search(r'Apache Maven (\d+\.\d+\.\d+)', result.stdout)
            if version_match:
                version = version_match.group(1)
                major_version = int(version.split('.')[0])
                return major_version >= 3
        elif build_tool == 'gradle':
            version_match = re.search(r'Gradle (\d+\.\d+)', result.stdout)
            if version_match:
                version = version_match.group(1)
                major_version = int(version.split('.')[0])
                return major_version >= 4
    return False
            