from ai4test.tools import *
import xml.etree.ElementTree as ET
import json
import os
import shutil
import math
from ai4test.ai4test_config import test_number, max_rounds


def xml_to_json(result_path):
    """
    Converts a JaCoCo XML report to a simplified JSON format.
    """
    output_path = os.path.abspath(result_path[:-4] + ".json")
    if os.path.exists(output_path):
        return

    src_path = os.path.abspath(result_path)
    tree = ET.parse(src_path)
    root = tree.getroot()

    result = {}
    for counter in root.findall('counter'):
        counter_type = counter.attrib['type'].lower()
        missed = int(counter.attrib['missed'])
        covered = int(counter.attrib['covered'])
        result[f'{counter_type}-missed'] = missed
        result[f'{counter_type}-covered'] = covered
        result[f'{counter_type}-rate'] = round(covered / (covered + missed), 3) if (covered + missed) > 0 else 0.0

    with open(output_path, "w") as f:
        json.dump(result, f)


def result_analysis(result_path=None):
    if not result_path:
        result_path = find_newest_result()
    if not os.path.exists(result_path):
        raise RuntimeError("Result Path not found!")
    print("\n" + result_path)

    for directory_path, directory_names, file_names in os.walk(result_path):
        for file_name in file_names:
            if file_name == 'coverage.xml':
                file_path = os.path.join(directory_path, file_name)
                xml_to_json(file_path)

    all_files_cnt = 0
    all_java_files_cnt = 0
    success_cnt = 0
    success_cnt_json = 0
    fail_cnt = 0
    runtemp_cnt = 0
    repair_success_cnt = 0
    repair_failed_cnt = 0
    project_name = ""
    repair_rounds = {i: 0 for i in range(2, max_rounds + 1)}

    for name in os.listdir(result_path):
        directory_name = os.path.join(result_path, name)
        if os.path.isdir(directory_name):
            if not project_name:
                project_name = parse_file_name(directory_name)[1]
            all_files_cnt += len(os.listdir(directory_name))
            for i in range(1, test_number + 1):
                sub_dir = os.path.join(directory_name, str(i))
                if os.path.exists(sub_dir):
                    runtemp_path = os.path.abspath(os.path.join(sub_dir, "runtemp/"))
                    if os.path.exists(runtemp_path):
                        runtemp_cnt += 1
                        shutil.rmtree(runtemp_path)

                    temp_dir = os.path.join(sub_dir, "temp")
                    coverage_path = os.path.join(temp_dir, "coverage.xml")
                    if os.path.exists(temp_dir):
                        for file_name in os.listdir(temp_dir):
                            if file_name.endswith(".java"):
                                all_java_files_cnt += 1
                                break
                    coverage_json = os.path.join(temp_dir, "coverage.json")
                    if os.path.exists(coverage_json):
                        success_cnt_json += 1

                    json_file_number = len(os.listdir(sub_dir)) - 1
                    if os.path.exists(coverage_path):
                        success_cnt += 1
                        if json_file_number > 3:
                            repair_success_cnt += 1
                            repair_rounds[math.ceil(json_file_number / 3)] += 1
                    else:
                        fail_cnt += 1
                        if json_file_number > 3:
                            repair_failed_cnt += 1

    print("Project name:        " + str(project_name))
    print("All files:           " + str(all_files_cnt))
    print("All java files:      " + str(all_java_files_cnt))
    print("Success:             " + str(success_cnt))
    print("Success json:        " + str(success_cnt_json))
    print("Fail:                " + str(fail_cnt))
    print("Repair success:      " + str(repair_success_cnt))
    print("Repair failed:       " + str(repair_failed_cnt))
    print("Repair rounds:       " + str(repair_rounds))
    print("runtemp counts:      " + str(runtemp_cnt))
    print()


def full_analysis(directory=result_dir):
    for root, dirs, files in os.walk(directory):
        for dir_name in dirs:
            if dir_name.startswith("scope_test"):
                result_analysis(os.path.join(root, dir_name))


if __name__ == '__main__':
    full_analysis("")