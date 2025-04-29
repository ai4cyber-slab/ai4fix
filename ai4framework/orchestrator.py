import sys
import time
import signal
import argparse
import os
try:
    from utils.logger import logger
    from config.common_config import ConfigManager
    from symbolic_execution.execution import SymbolicExecution
    from sast.sast_orchestrator import SASTOrchestrator
    from utils.issues_merger import JSONCombiner
    from utils.plugin_json_converter import JsonPluginConverter
    from generation.patch_applier import PatchApplier
    from generation.patch_generation import PatchGenerator
    from classification.security_classifier import SecurityClassifier
    from ai4test import run
except KeyboardInterrupt:
    sys.exit(0)

class WorkflowFramework:
    """
    A class that orchestrates the execution of various security analysis workflows.
    This framework integrates different components such as SAST (Static Application Security Testing),
    security classification, and symbolic execution to perform a comprehensive security analysis
    of a software project.
    """

    def __init__(self, commit_sha, skip_patches=False, sast_rerun=False, automatic_application=False, single_file=None, count_issues=False, external_json=False):
        try:
            self.config = ConfigManager.get_config(commit_sha)
        except Exception as e:
            logger.error(f"Please create and fill correctly your config.properties file and set it under the root of your project. To fix: {e}")
            sys.exit(1)
        try:
            self.single_file = single_file
            self.sast_rerun = sast_rerun
            self.skip_patches = skip_patches
            self.automatic_application = automatic_application
            self.count_issues = count_issues
            self.external_json = external_json

            self.sast = SASTOrchestrator(self.config, self.single_file)
            self.security_classifier = SecurityClassifier(self.config)
            self.symbolic_execution = SymbolicExecution(self.config, self.single_file)
            self.issues_merger = JSONCombiner(self.config, single_file=self.single_file, skip_patches=self.skip_patches, external_json=self.external_json)
            self.json_converter = JsonPluginConverter(self.config, single_file=self.single_file)
            signal.signal(signal.SIGINT, self.handle_signal)
            signal.signal(signal.SIGTERM, self.handle_signal)
            logger.info("Signal handlers for SIGINT and SIGTERM registered.")
        except Exception as e:
            logger.error(f"An error occurred during initialization: {e}")
            sys.exit(1)

    def execute_workflow(self):
        logger.info("Starting workflow execution")
        start_time = time.time()
        total_issue_count = 0
        warnings_dict_original = {}
        try:
            rounds_count = int(self.config.get("DEFAULT", "config.rounds_count", fallback=1))
            if self.single_file:
                rounds_count = 1

            for i in range(1, rounds_count + 1):
                logger.info(f"Starting round {i}")
                if self.skip_patches and self.external_json:
                    self.sast.run_all() if i == 1 else self.sast.run_all(is_initial_round=False)
                if not self.external_json:
                    self.sast.run_all() if i == 1 else self.sast.run_all(is_initial_round=False)
                if not self.sast_rerun:
                    if self.skip_patches and self.external_json:
                        self.security_classifier.classify()
                        self.symbolic_execution.analyze()
                    if not self.external_json:
                        self.security_classifier.classify()
                        self.symbolic_execution.analyze()
                    logger.info("Analysis completed")

                    warnings_dict_original = self.issues_merger.run(self.count_issues)
                    total_issue_count = sum(warnings_dict_original.values())
                    logger.info("Issues merger run completed")

                    if not self.skip_patches and not self.sast_rerun and not self.count_issues:
                        patch_generator = PatchGenerator(self.config, warnings_dict_original, i, single_file=self.single_file, external_json = self.external_json)
                        patch_generator.main()
                        logger.info("Patch generation completed")
                    if not self.count_issues:
                        self.json_converter.process()
                        logger.info("JSON conversion completed")

                    if self.automatic_application:
                        PatchApplier(self.config).apply_patches()
                        logger.info("Patch application completed")

        except KeyboardInterrupt:
            logger.info("SIGINT received. Gracefully stopping workflow.")
            self.json_converter.process()
            logger.info("Progress saved successfully.")
            sys.exit(0)
        except Exception as e:
            logger.error(f"An error occurred: {e}")
        finally:
            elapsed_time = time.time() - start_time
            logger.info(f"Workflow execution completed in {elapsed_time:.2f} seconds")
            if self.count_issues:
                print(f"Total issue count: {total_issue_count}")
                print(f"warnings_dict_original: {warnings_dict_original}")

            RESET_COLOR = "\033[0m"
            BOLD_BLUE = "\033[1;34m"
            BOLD_MAGENTA = "\033[1;35m"
            print(
                f"{BOLD_BLUE}To copy the '.ai4framework' folder from the container to your local machine, "
                f"use the following command in your local terminal (outside the container):\n\n"
                f"{BOLD_BLUE}docker cp {0 or '<container_id>'}:{os.environ.get('PROJECT_PATH') or '/path/in/container'}/.ai4framework \"{0 or '/path/on/local/machine'}\"\n\n"
                f"{RESET_COLOR}{BOLD_MAGENTA}Ensure you replace <container_id> with the actual container ID and paths as needed.{RESET_COLOR}"
            )
            logger.debug(
                f"{BOLD_BLUE}To copy the '.ai4framework' folder from the container to your local machine, "
                f"use the following command in your local terminal (outside the container):\n\n"
                f"{BOLD_BLUE}docker cp {0 or '<container_id>'}:{os.environ.get('PROJECT_PATH') or '/path/in/container'}/.ai4framework \"{0 or '/path/on/local/machine'}\"\n\n"
                f"{RESET_COLOR}{BOLD_MAGENTA}Ensure you replace <container_id> with the actual container ID and paths as needed.{RESET_COLOR}"
            )

    def handle_signal(self, signal_number, frame):
        """Handle termination signals (SIGINT, SIGTERM) for graceful shutdown."""
        logger.info(f"Signal {signal_number} received. Gracefully stopping workflow.")
        self.json_converter.process()
        logger.info("Progress saved successfully.")
        sys.exit(0)



def run_ai4test(args, config=None):

    ai4test_args = []
    if args.scope_test:
        ai4test_args.append("--scope-test")
    if args.class_name:
        ai4test_args += ["--class-name", args.class_name]
    if args.method_name:
        ai4test_args += ["--method-name", args.method_name]
    if args.multiprocess:
        ai4test_args.append("--multiprocess")
    if args.no_repair:
        ai4test_args.append("--no-repair")
    if args.confirmed:
        ai4test_args.append("--confirmed")

    run.main(ai4test_args, config=config)


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description="Executes the security analysis workflow.")

        parser.add_argument("-c", "--commit_sha", help="The hash of the commit, with the modified files to be analyzed. If not provided, the whole project will be analyzed.")
        parser.add_argument("--skip-patches", action="store_true", help="If provided, the patches part will be skipped.")
        parser.add_argument("--sast-rerun", action="store_true", help="If provided, issues will be generated for the new java files contents.")
        parser.add_argument("--auto", action="store_true", help="If provided, patches will be applied automatically after the analysis complete.")
        parser.add_argument("--single-file", help="The path of the file to be analyzed.")
        parser.add_argument("--count-issues", action="store_true", help="If provided, only the count of the issues found will be returned.")
        parser.add_argument("--external-json", action="store_true", help="If provided, working with an exteral JSON file named output.json.")
        parser.add_argument("--skip-ai4fix", action="store_true", help="If provided, only AI4Test will run, skipping the security analysis workflow.")

        parser.add_argument("--ai4test", action="store_true", help="Run AI4Test process.")
        parser.add_argument("--scope-test", action="store_true", help="Enable scope test mode (for ai4test)")
        parser.add_argument("--class-name", type=str, help="Class name to use in ai4test scope test mode")
        parser.add_argument("--method-name", type=str, help="Method name to use in ai4test scope test mode")
        parser.add_argument("--multiprocess", action="store_true", help="Enable multiprocessing (for ai4test)")
        parser.add_argument("--no-repair", dest="no_repair", action="store_true", help="Disable repair (for ai4test)")
        parser.add_argument("--confirmed", action="store_true", help="Skip user confirmation (for ai4test)")

        args = parser.parse_args()
        if args.ai4test and args.scope_test and not args.class_name:
            parser.error("--class-name is required when --scope-test is used with --ai4test")

        if not args.skip_ai4fix:
            framework = WorkflowFramework(
                commit_sha=args.commit_sha,
                skip_patches=args.skip_patches,
                sast_rerun=args.sast_rerun,
                automatic_application=args.auto,
                single_file=args.single_file,
                count_issues=args.count_issues,
                external_json=args.external_json
            )
            framework.execute_workflow()
            
        if args.ai4test or args.skip_ai4fix:
            if not args.skip_ai4fix:
                run_ai4test(args, framework.config)
            else:
                config = ConfigManager.get_config(args.commit_sha)
                run_ai4test(args, config)

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user.")
    except Exception as e:
        logger.error("An unexpected error occurred. Please try again or contact support.")
        print(e)
    finally:
        sys.exit(0)