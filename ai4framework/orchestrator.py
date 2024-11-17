import os
import sys
import subprocess
from symbolic_execution.execution import SymbolicExecution
from config.common_config import ConfigManager
from utils.logger import logger
from classification.security_classifier import SecurityClassifier
from sast.sast_orchestrator import SASTOrchestrator
from patch_generation.patch_generator import PatchGenerator
from utils.issues_merger import JSONCombiner
from utils.plugin_json_converter import JsonPluginConverter
import time
import signal
import argparse


class WorkflowFramework:
    """
    A class that orchestrates the execution of various security analysis workflows.
    This framework integrates different components such as SAST (Static Application Security Testing),
    security classification, and symbolic execution to perform a comprehensive security analysis
    of a software project.
    """

    def __init__(self, project_root, dir_to_analyze, skip_patches=False, sast_rerun=False):
        self.config = ConfigManager.get_config(project_root, dir_to_analyze)
        self.sast_rerun = sast_rerun
        self.skip_patches = skip_patches

        self.sast = SASTOrchestrator(self.config)
        self.security_classifier = SecurityClassifier(self.config)
        self.symbolic_execution = SymbolicExecution(self.config)
        self.issues_merger = JSONCombiner(self.config)
        self.json_converter = JsonPluginConverter(self.config)

    def execute_workflow(self):
        logger.info("Starting workflow execution")
        start_time = time.time()

        self.sast.run_all()

        if not self.sast_rerun:
            # self.security_classifier.classify()
            # self.symbolic_execution.analyze()
            pass

        warnings_dict_original = self.issues_merger.run()

        if not self.skip_patches and not self.sast_rerun:
            patch_generator = PatchGenerator(self.config, warnings_dict_original)
            patch_generator.main()

        self.json_converter.process()

        elapsed_time = time.time() - start_time
        logger.info(f"Workflow execution completed in {elapsed_time:.2f} seconds")


def kill_rg_processes():
    """
    Function to kill any lingering 'rg' (ripgrep) processes.
    """
    try:
        with subprocess.Popen("ps aux | grep rg | grep -v grep | awk '{print $2, $11}'", shell=True, stdout=subprocess.PIPE, text=True) as process:
            result = process.communicate()[0]
            processes = result.strip().split('\n')

            for process in processes:
                if process:
                    pid, name = process.split(' ', 1)
                    os.kill(int(pid), signal.SIGKILL)
    except Exception as e:
        print(f"Error killing processes: {e}")


def signal_handler(sig, frame):
    """
    Handle termination signals (e.g., Ctrl+C) and perform cleanup.
    """
    kill_rg_processes()
    sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Execute the security analysis workflow.")

    parser.add_argument("-r", "--project_root", help="Path to the root directory of your project.")
    parser.add_argument("-d", "--dir_to_analyze", help="Path to the directory that should be analyzed. If empty, the root will be used.")
    parser.add_argument("--skip-patches", action="store_true", help="If provided, the patches part will be skipped.")
    parser.add_argument("--sast-rerun", action="store_true", help="If provided, issues will be generated for the new java files contents.")

    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


    framework = WorkflowFramework(
        project_root=args.project_root,
        dir_to_analyze=args.dir_to_analyze,
        skip_patches=args.skip_patches,
        sast_rerun=args.sast_rerun
    )

    framework.execute_workflow()
    kill_rg_processes()