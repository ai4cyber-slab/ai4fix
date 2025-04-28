from ai4test.tools import *
from ai4test.call_model import start_whole_process
from ai4test.database import database
from ai4test.task import Task
from ai4test.ai4test_logger import logger
import sys
from pathlib import Path
import shutil
from ai4test.generate_html_report import generate_report
from ai4test.ai4test_config import result_dir, dataset_dir, project_dir
import os
import re
import datetime



db = database()


def create_dataset_result_folder(direction):
    """
    Create a new folder for this scope test.
    :param direction: The direction of this scope test.
    :return: The path of the new folder.
    """
    now = datetime.datetime.now()
    time_str = now.strftime("%Y%m%d%H%M%S")
    result_path = os.path.join(result_dir, "scope_test%" + time_str + "%" + direction)
    if not os.path.exists(result_path):
        os.makedirs(result_path)
    else:
        raise Exception("Result folder already exists.")
    return result_path


def start_generation(sql_query, multiprocess=True, repair=True, confirmed=False, source_files=[], pre_report_path=None):
    """
    Start the scope test.
    :param multiprocess: if it needs to
    :param repair:
    :param sql_query:
    :return:
    """
    match = re.search(r"project_name\s*=\s*'([\w-]*)'", sql_query)
    if match:
        project_name = match.group(1)
        logger.info(f"target project: {project_name}")
    else:
        raise RuntimeError("One project at one time.")
    remove_single_test_output_dirs(get_project_abspath())

    method_ids = [x[0] for x in db.select(script=sql_query)]
    result = db.select(script=sql_query)
    if not method_ids:
        raise Exception("Method ids cannot be None.")
    if not isinstance(method_ids[0], str):
        method_ids = [str(i) for i in method_ids]
    print("The number of methods is ", len(method_ids), ".")
    record = "This is a record of a scope test.\n"
    if not confirmed:
        confirm = input("Are you sure to start the scope test? (y/n): ")
        if confirm != "y":
            logger.warning("Scope test cancelled based on user request. Shutting down ...")
            sys.exit(0)
            return

    result_path = create_dataset_result_folder("")

    record += "Result path: " + result_path + "\n"
    record += 'SQL script: "' + sql_query + '"\n'
    record += "Included methods: " + str(method_ids) + "\n"

    record_path = os.path.join(result_path, "record.txt")
    with open(record_path, "w") as f:
        f.write(record)
    logger.info(f"The record has been saved at {record_path}")

    source_dir = os.path.join(dataset_dir, "direction_1")

    start_whole_process(source_dir, result_path, multiprocess=multiprocess, repair=repair, method_ids=method_ids)
    logger.info(f"WHOLE PROCESS FINISHED")
    project_path = os.path.abspath(project_dir)
    logger.info(f"START ALL TESTS")
    compile_time, error_time, post_report = Task.all_test(result_path, project_path, source_files)
    test_results_dir = find_result_in_projects()
    try:
        with open(record_path, "a") as f:
            f.write("Whole test result at: " + test_results_dir + "\n")
    except Exception as e:
        logger.error(f"Cannot save whole test result: {e}.")
      
    try:
        if pre_report_path and os.path.exists(pre_report_path):
            source = Path(pre_report_path)

            post_report_path = Path(post_report)
            destination_dir = post_report_path.parent.parent
            destination = destination_dir / source.name

            if not destination.exists():
                destination_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))
    except Exception as e:
        print("Error:", str(e))

    logger.info("SCOPE TEST FINISHED")

    try:
        if os.path.exists(destination) and os.path.exists(post_report_path):
            output_path = Path(post_report_path).parent / "final-coverage-diff.html"
            generate_report(str(destination), str(post_report_path), str(output_path))
    except Exception as e:
        print("Error during generation of final diff report: ", str(e))







if __name__ == '__main__':
    sql_query = "SELECT id FROM method WHERE project_name='struts' AND class_name='ActionContext' AND method_name='withServletResponse' AND is_constructor=0;"
    start_generation(sql_query, multiprocess=False, repair=True, confirmed=False)
