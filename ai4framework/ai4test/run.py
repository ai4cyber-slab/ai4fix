import os.path
import sys
import time
import argparse
import shutil

from ai4test.tools import *
from ai4test.database import *
from ai4test.parse_data import parse_data
from ai4test.export_data import export_data
from ai4test.scope_test import start_generation
from ai4test.parse_xml import result_analysis
from ai4test.task import Task
from ai4test.ai4test_config import dataset_dir, JACOCO_AGENT, JACOCO_CLI, database_name, refresh, project_dir, ai4test_dir
from tqdm import tqdm
from ai4test.ai4test_logger import logger
from ai4test.download_dependencies import *
from ai4test.generate_before_report import generate_before_report
from ai4test.cover2cover import jacoco2cobertura
from ai4test.dependency_checker import generate_report

db_name: str = database_name

def clear_dataset():
    """
    Clear the dataset folder.
    """
    if os.path.exists(dataset_dir):
        shutil.rmtree(dataset_dir)

def run(scope_test=False, class_name=None, method_name=None, multiprocess=False, repair=True, confirmed=False, config=None):
    """
    AI4Test entry point.
    
    Args:
        scope_test (bool): Whether to run in scope test mode
        class_name (str): Class name to test in scope test mode
        method_name (str): Method name to test in scope test mode
        multiprocess (bool): Whether to use multiprocessing
        repair (bool): Whether to perform test repair
        confirmed (bool): Whether to skip user confirmation
        config (ConfigParser): Configuration object
    """

    if config.get("DEFAULT", "config.build_tool").strip().lower() != 'maven':
        print("[ERROR] AI4Test supports Maven projects only.")
        sys.exit(5)
    
    for _ in tqdm(range(2), desc="Starting in", unit="s"):
        time.sleep(2)

    print(f"Current database in use is '{db_name}'.")

    drop_table()
    create_table()

    info_path = Task.parse(project_dir)
    parse_data(info_path)
    clear_dataset()
    export_data()

    project_name = os.path.basename(os.path.normpath(project_dir))

    if scope_test:
        logger.info("scope test mode")
        sql_query = f"""
            SELECT id FROM method WHERE project_name='{project_name}' 
            AND class_name='{class_name}' 
            {"AND method_name='" + method_name + "'" if method_name else ""}
            AND is_constructor=0 AND is_public=1;
        """
    else:
        sql_query = f"""
            SELECT id FROM method WHERE project_name='{project_name}' AND is_public=1 AND is_constructor=0;
        """
    try:
        pom_path = find_main_pom(project_dir)
        if pom_path:
            versions = get_mockito_and_junit_versions(pom_path=pom_path)
            jar_paths = download_mockito_dependencies()
        else:
            print(f"pom.xml not found in project root {project_dir}")
        # import pdb; pdb.set_trace()
        refresh()
        # generate coverage report before running the process
        jacoco_report_path, sourcefiles = generate_before_report(project_root=project_dir, jacoco_agent_path=JACOCO_AGENT, jacoco_cli_path=JACOCO_CLI, config=config)
        cobertura_report_path = jacoco2cobertura(filename=jacoco_report_path, state="pre")


        start_generation(sql_query, multiprocess=multiprocess, repair=repair, confirmed=confirmed, source_files=sourcefiles, pre_report_path=cobertura_report_path)
        result_analysis()
        time.sleep(1)
    except Exception as e:
        print("Error from run:", str(e))
    finally:
        remove_jar_files(jar_paths)
    return versions


def main(custom_args=None, config=None):

    parser = argparse.ArgumentParser(description="Test case generator")
    parser.add_argument('--scope-test', action='store_true', help='Enable scope test mode')
    parser.add_argument('--class-name', type=str, help='Class name to use in scope test mode')
    parser.add_argument('--method-name', type=str, help='Method name to use in scope test mode')
    parser.add_argument('--multiprocess', action='store_true', help='Enable multiprocessing (default: False)')
    parser.add_argument('--no-repair', dest='repair', action='store_false', help='Disable repair (default: True)')
    parser.add_argument('--confirmed', action='store_true', help='Skip manual confirmation')
    parser.set_defaults(repair=True)

    args = parser.parse_args(custom_args)

    if args.scope_test and not args.class_name:
        parser.error("--class-name is required when --scope-test is used")

    versions = run(
        scope_test=args.scope_test,
        class_name=args.class_name,
        method_name=args.method_name,
        multiprocess=args.multiprocess,
        repair=args.repair,
        confirmed=args.confirmed,
        config=config
    )

    pom_path = os.path.join(project_dir, 'pom.xml')
    expected_versions = {
        "mockito-core": versions["mockito"],
        "mockito-junit-jupiter": versions["mockito"],
        "mockito-inline": versions["mockito"],
        "junit": versions["junit"]
    }

    dep_guide_path = os.path.join(ai4test_dir, 'dependencies-guide.txt')
    generate_report(pom_path, expected_versions, output_file=dep_guide_path)

    print(f"[INFO] Dependency check completed. Report saved to {dep_guide_path}")