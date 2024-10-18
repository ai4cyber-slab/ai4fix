import signal
import sys
import os
import subprocess
from symbolic_execution.execution import SymbolicExecution
from config.common_config import ConfigManager
from utils.logger import logger
from classification.security_classifier import SecurityClassifier
import sast.sast_orchestrator
from patch_generation.patch_generator import PatchGenerator
from test_generation.test_generator import TestGenerator
from utils.issues_merger import JSONCombiner
from utils.plugin_json_converter import JsonPluginConverter
import time
import re
import argparse


class WorkflowFramework:
    """
    A class that orchestrates the execution of various security analysis workflows.
    This framework integrates different components such as SAST (Static Application Security Testing),
    security classification, and symbolic execution to perform a comprehensive security analysis
    of a software project.
    """

    def __init__(self, skip_patches=False, sast_rerun=False):
        self.config = ConfigManager.get_config()
        self.sast = sast.sast_orchestrator.SASTOrchestrator(self.config)
        self.security_classifier = SecurityClassifier(self.config)
        self.symbolic_execution = SymbolicExecution(self.config)
        self.patch_generator = PatchGenerator(self.config)
        # self.test_generator = TestGenerator(self.config)
        self.issues_merger = JSONCombiner(self.config)
        self.json_converter = JsonPluginConverter(self.config)
        self.skip_patches = skip_patches
        self.sast_rerun = sast_rerun

    def execute_workflow(self):
        logger.info("Starting workflow execution")
        start_time = time.time()

        # Run SAST analysis first
        self.sast.run_all()

        # If sast_rerun is NOT enabled, run the security classifier and symbolic execution
        if not self.sast_rerun:
            self.security_classifier.classify()
            self.symbolic_execution.analyze()

        # Merge issues regardless of whether sast_rerun or skip_patches is enabled
        self.issues_merger.run()


        if not self.skip_patches and not self.sast_rerun:
            self.patch_generator.main()
            

        # Process the JSON conversion after all steps
        self.json_converter.process()

        elapsed_time = time.time() - start_time
        logger.info(f"Workflow execution completed in {elapsed_time:.2f} seconds")


def kill_rg_processes():
    """
    Function to kill any lingering 'rg' (ripgrep) processes and print their names.
    """
    try:
        with subprocess.Popen("ps aux | grep rg | grep -v grep | awk '{print $2, $11}'", shell=True, stdout=subprocess.PIPE, text=True) as process:
            result = process.communicate()[0]
            processes = result.strip().split('\n')

            for process in processes:
                if process:
                    pid, name = process.split(' ', 1)
                    os.kill(int(pid), 9)

    except Exception as e:
        print(f"Error killing processes: {e}")


def signal_handler(sig, frame):
    """
    Handle termination signals (e.g., Ctrl+C) and perform cleanup.
    """
    kill_rg_processes()
    sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Execute the security analysis workflow.')
    parser.add_argument('--skip-patches', action='store_true', help='If provided, the patches part will be skipped.')
    parser.add_argument('--sast-rerun', action='store_true', help='If provided, issues will be generated for the new java files contents.')
    args, unknown = parser.parse_known_args()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize the framework with the parsed arguments
    framework = WorkflowFramework(skip_patches=args.skip_patches, sast_rerun=args.sast_rerun)

    # Execute the workflow
    framework.execute_workflow()

    # Kill any remaining rg processes
    kill_rg_processes()