import copy
import os
import sys
import time
from ai4test.tools import *
import random
import concurrent.futures
import javalang
import jinja2
from ai4test.task import Task
import json
from typing import Any
from ai4test.ai4test_logger import logger
from ai4test.ai4test_config import MAX_PROMPT_TOKENS, key, model, MAX_PROMPT_TOKENS, max_rounds, TEMPLATE_ERROR, MIN_ERROR_TOKENS, TEMPLATE_NO_DEPS, TEMPLATE_WITH_DEPS, test_number, process_number, dep_config, azure_api_version, azure_endpoint, provider

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.llm_configuration import llm_response


env = jinja2.Environment(loader=jinja2.FileSystemLoader('/app/prompt'))


def call_model(messages, save_path):
    if get_messages_tokens(messages) > MAX_PROMPT_TOKENS:
        return False
    max_try = 3
    while max_try:
        try:
            response = llm_response(provider=provider, model=model, api_key=key, messages=messages, endpoint=azure_endpoint, api_v=azure_api_version)
            with open(save_path, "w") as f:
                json.dump(response, f, indent=2)
            return True
        except Exception as e:
            logger.error(str(e))
            if "maximum context length".lower() in str(e).lower() or "context window".lower() in str(e).lower():
                break
            time.sleep(10)
            if "rate limit" in str(e).lower() or "capacity" in str(e).lower() or "overloaded" in str(e).lower():
                sleep_time = random.randint(60, 120)
                time.sleep(sleep_time)
        max_try -= 1
    return False

def generate_prompt(template_name, context: dict):
    template = env.get_template(template_name)
    prompt = template.render(context)

    return prompt


def load_context_file(context_file):
    if isinstance(context_file, str):
        with open(context_file, "r") as f:
            return json.load(f)
    return context_file


def generate_messages(template_name, context_file):
    context = load_context_file(context_file)
    messages = []

    system_name = f"{template_name.split('.')[0]}_system.jinja2"
    system_path = os.path.join("/app/prompt", system_name)
    if os.path.exists(system_path):
        versions_context = {
            "junit_version": str(dep_config.get("DEFAULT", "JUNIT_VERSION")).split(".")[0],
            "mockito_version": str(dep_config.get("DEFAULT", "MOCKITO_VERSION")).split(".")[0]
        }
        system_message = generate_prompt(system_name, versions_context)
        messages.append({"role": "system", "content": system_message})

    user_message = generate_prompt(template_name, context)
    messages.append({"role": "user", "content": user_message})

    return messages


def process_error_message(error_message, allowed_tokens):
    if allowed_tokens <= 0:
        return ""
    while count_tokens(error_message) > allowed_tokens:
        if len(error_message) > 50:
            error_message = error_message[:-50]
        else:
            break
    return error_message


def syntactic_check(code):
    if is_syntactic_correct(code):
        return False, code
    else:
        stop_point = [";", "}", "{", " "]
        for idx in range(len(code) - 1, -1, -1):
            if code[idx] in stop_point:
                code = code[:idx + 1]
                break
        left_bracket = code.count("{")
        right_bracket = code.count("}")
        for idx in range(left_bracket - right_bracket):
            code += "}\n"

        if is_syntactic_correct(code):
            return True, code

        matches = list(re.finditer(r"(?<=\})[^\}]+(?=@)", code))
        if matches:
            code = code[:matches[-1].start() + 1]
            left_count = code.count("{")
            right_count = code.count("}")
            for _ in range(left_count - right_count):
                code += "\n}"
        if is_syntactic_correct(code):
            return True, code
        else:
            return True, ""


def is_syntactic_correct(code):
    try:
        javalang.parse.parse(code)
        return True
    except Exception as e:
        return False


def extract_code(string):
    if is_syntactic_correct(string):
        return True, string, False

    has_code = False
    extracted_code = ""
    has_syntactic_error = False

    pattern = r"```[java]*([\s\S]*?)```"

    matches = re.findall(pattern, string)
    if matches:
        filtered_matches = [match.strip() for match in matches if
                            "@Test" in match and "class" in match and "import" in match]
        if filtered_matches:
            for match in filtered_matches:
                has_syntactic_error, extracted_code = syntactic_check(match)
                if extracted_code != "":
                    has_code = True
                    break

    if not has_code:
        if "```java" in string:
            separate_string = string.split("```java")[1]
            if "@Test" in separate_string:
                has_syntactic_error, temp_code = syntactic_check(separate_string)
                if temp_code != "":
                    extracted_code = temp_code
                    has_code = True
        elif "```" in string:
            separate_strings = string.split("```")
            for separate_string in separate_strings:
                if "@Test" in separate_string:
                    has_syntactic_error, temp_code = syntactic_check(separate_string)
                    if temp_code != "":
                        extracted_code = temp_code
                        has_code = True
                        break
        else:
            allowed = ["import", "packages", "", "@"]
            code_lines = string.split("\n")
            start, anchor, end = -1, -1, -1
            allowed_lines = [False for _ in range(len(code_lines))]
            left_brace = {x: 0 for x in range(len(code_lines))}
            right_brace = {x: 0 for x in range(len(code_lines))}
            for i, line in enumerate(code_lines):
                left_brace[i] += line.count("{")
                right_brace[i] += line.count("}")
                striped_line = line.strip()

                for allow_start in allowed:
                    if striped_line.startswith(allow_start):
                        allowed_lines[i] = True
                        break

                if re.search(r'public class .*Test', line) and anchor == -1:
                    anchor = i

            if anchor != -1:
                start = anchor
                while start:
                    if allowed_lines[start]:
                        start -= 1

                end = anchor
                left_sum, right_sum = 0, 0
                while end < len(code_lines):
                    left_sum += left_brace[end]
                    right_sum += right_brace[end]
                    if left_sum == right_sum and left_sum >= 1 and right_sum >= 1:
                        break
                    end += 1

                temp_code = "\n".join(code_lines[start:end + 1])
                has_syntactic_error, temp_code = syntactic_check(temp_code)
                if temp_code != "":
                    extracted_code = temp_code
                    has_code = True

    extracted_code = extracted_code.strip()
    return has_code, extracted_code, has_syntactic_error


def extract_and_run(input_string, output_path, class_name, method_id, test_num, project_name, package):
    result = {}
    has_code, extracted_code, has_syntactic_error = extract_code(input_string)
    if not has_code:
        return False, True
    result["has_code"] = has_code
    result["source_code"] = extracted_code
    if package:
        result["source_code"] = repair_package(extracted_code, package)
    result["has_syntactic_error"] = has_syntactic_error
    
    temp_dir = os.path.join(os.path.dirname(output_path), "temp")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    export_method_test_case(os.path.abspath(temp_dir), class_name, method_id, test_num,
                            change_class_name(result["source_code"], class_name, method_id, test_num))

    response_dir = os.path.abspath(os.path.dirname(output_path))
    target_dir = os.path.abspath(os.environ.get('PROJECT_PATH'))
    Task.test(response_dir, target_dir)

    if "compile_error.txt" in os.listdir(temp_dir):
        with open(os.path.join(temp_dir, "compile_error.txt"), "r") as f:
            result["compile_error"] = f.read()

    if "runtime_error.txt" in os.listdir(temp_dir):
        with open(os.path.join(temp_dir, "runtime_error.txt"), "r") as f:
            result["runtime_error"] = f.read()
    if "coverage.html" in os.listdir(temp_dir):
        result["coverage_html"] = True
    if "coverage.xml" in os.listdir(temp_dir):
        result["coverage_xml"] = True
    if "coverage.csv" in os.listdir(temp_dir):
        result["coverage_csv"] = True
    test_passed = False
    
    if "compile_error" not in result and "runtime_error" not in result:
        test_passed = True

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    return test_passed, False


def remain_prompt_tokens(messages):
    return MAX_PROMPT_TOKENS - get_messages_tokens(messages)


def whole_process(test_num, base_name, base_dir, repair, submits, total):
    progress = '[' + str(submits) + ' / ' + str(total) + ']'
    save_dir = os.path.join(base_dir, str(test_num))
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    run_temp_dir = os.path.join(save_dir, "runtemp")

    steps, rounds = 0, 0
    method_id, project_name, class_name, method_name = parse_file_name(base_name)

    with open(get_dataset_path(method_id, project_name, class_name, method_name, "raw"), "r") as f:
        raw_data = json.load(f)

    package = raw_data["package"]
    imports = raw_data["imports"]

    with open(get_dataset_path(method_id, project_name, class_name, method_name, 1), "r") as f:
        context_d_1 = json.load(f)
    with open(get_dataset_path(method_id, project_name, class_name, method_name, 3), "r") as f:
        context_d_3 = json.load(f)

    def _remove_imports_context(strings):
        if imports:
            strings = strings.replace(imports, "")
        if package:
            strings = strings.replace(package, "")
        strings = strings.strip()
        return strings

    try:
        while rounds < max_rounds:
            steps += 1
            rounds += 1
            logger.info(f"{progress} {method_id} test_{str(test_num)} Calling Model... rounds {rounds}")
            model_file_name = os.path.join(save_dir, str(steps) + "_model_" + str(rounds) + ".json")
            
            if rounds != 1:
                last_round_result = get_latest_file(save_dir)
                with open(last_round_result, "r") as f:
                    last_round_result = json.load(f)
                last_raw = get_latest_file(save_dir, suffix="raw")
                with open(last_raw, "r") as f:
                    last_raw = json.load(f)

                context = {"class_name": context_d_1["class_name"], "method_name": context_d_1["focal_method"],
                           "unit_test": last_raw["source_code"], "method_code": context_d_1["information"],
                            "junit_version": str(dep_config.get("DEFAULT", "JUNIT_VERSION")).split(".")[0], "mockito_version": str(dep_config.get("DEFAULT", "MOCKITO_VERSION")).split(".")[0]}
                
                messages = generate_messages(TEMPLATE_ERROR, context)
                allow_tokens = remain_prompt_tokens(messages)
                if allow_tokens < MIN_ERROR_TOKENS:
                    context["method_code"] = _remove_imports_context(context["method_code"])
                    messages = generate_messages(TEMPLATE_ERROR, context)
                    allow_tokens = remain_prompt_tokens(messages)
                if allow_tokens < MIN_ERROR_TOKENS:
                    context["method_code"] = context_d_3["full_fm"]
                    messages = generate_messages(TEMPLATE_ERROR, context)
                    allow_tokens = remain_prompt_tokens(messages)
                if allow_tokens < MIN_ERROR_TOKENS:
                    context["method_code"] = _remove_imports_context(context_d_3["full_fm"])
                    messages = generate_messages(TEMPLATE_ERROR, context)
                    allow_tokens = remain_prompt_tokens(messages)
                if allow_tokens >= MIN_ERROR_TOKENS:
                    if "compile_error" in last_round_result:
                        context["error_type"] = "compiling"
                        error_mes = process_error_message(last_round_result["compile_error"], allow_tokens)
                        context["error_message"] = error_mes
                    if "runtime_error" in last_round_result:
                        context["error_type"] = "running"
                        error_mes = process_error_message(last_round_result["runtime_error"], allow_tokens)
                        context["error_message"] = error_mes
                else:
                    logger.error(f"{progress} {method_id}, Tokens not enough, test fatal error...")
                    break
                if "compile_error" not in last_round_result and "runtime_error" not in last_round_result:
                    logger.error(f"{progress} {method_id}, Timeout error, test fatal error...")
                    break
                messages = generate_messages(TEMPLATE_ERROR, context)
            else:
                if not context_d_3["c_deps"] and not context_d_3["m_deps"]:
                    context = copy.deepcopy(context_d_1)
                    messages = generate_messages(TEMPLATE_NO_DEPS, context)
                    if remain_prompt_tokens(messages) < 0:
                        context["information"] = _remove_imports_context(context["information"])
                        messages = generate_messages(TEMPLATE_NO_DEPS, context)
                        if remain_prompt_tokens(messages) < 0:
                            messages = []
                else:
                    context = copy.deepcopy(context_d_3)
                    messages = generate_messages(TEMPLATE_WITH_DEPS, context)
                    if remain_prompt_tokens(messages) < 0:
                        context["full_fm"] = _remove_imports_context(context["full_fm"])
                        messages = generate_messages(TEMPLATE_WITH_DEPS, context)
                        if remain_prompt_tokens(messages) < 0:
                            messages = []

                if not messages:
                    context = copy.deepcopy(context_d_1)
                    context["information"] = context_d_3["full_fm"]
                    messages = generate_messages(TEMPLATE_NO_DEPS, context)
                    if remain_prompt_tokens(messages) < 0:
                        context["information"] = _remove_imports_context(context["information"])
                        messages = generate_messages(TEMPLATE_NO_DEPS, context)
                        if remain_prompt_tokens(messages) < 0:
                            logger.error(f"{progress}, Tokens not enough, test fatal error...")
                            break

            status = call_model(messages, model_file_name)
            if not status:
                logger.error(f"{progress}, model Fail processing messages")
                break

            with open(model_file_name, "r") as f:
                model_result = json.load(f)

            steps += 1

            raw_file_name = os.path.join(save_dir, str(steps) + "_raw_" + str(rounds) + ".json")

            input_string = model_result['message']
            test_passed, fatal_error = extract_and_run(input_string, raw_file_name, class_name, method_id, test_num,
                                                       project_name,
                                                       package)

            if test_passed:
                logger.info(f"{progress}, {method_id} test_{str(test_num)} steps {steps} rounds {rounds} test passed")
                break

            if not os.path.exists(raw_file_name):
                logger.error(f"{progress}, {method_id} test_{str(test_num)} steps {steps} rounds {rounds} no code in raw result")
                break

            with open(get_latest_file(save_dir), "r") as f:
                raw_result = json.load(f)

            steps += 1
            imports_file_name = os.path.join(save_dir, str(steps) + "_imports_" + str(rounds) + ".json")
            source_code = raw_result["source_code"]
            source_code = repair_imports(source_code, imports)
            test_passed, fatal_error = extract_and_run(source_code, imports_file_name, class_name, method_id, test_num,
                                                       project_name,
                                                       package)
            if test_passed:
                logger.info(f"{progress}, {method_id} test_{str(test_num)} steps {steps} rounds {rounds} test passed")
                break
            if fatal_error:
                logger.error(f"{progress}, {method_id} test_{str(test_num)} steps {steps} rounds {rounds} fatal error")
                break

            logger.warning(f"{progress}, {method_id} test_{str(test_num)} Test failed, fixing... rounds {rounds}")
            if not repair:
                break
    except Exception as e:
        logger.error(f"{progress} {str(e)}")
    if os.path.exists(run_temp_dir):
        run_temp_dir = os.path.abspath(run_temp_dir)
        shutil.rmtree(run_temp_dir)


def start_whole_process(source_dir, result_path, method_ids=None, multiprocess=False, repair=True):
    file_paths = []
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            if not file.endswith(".json"):
                continue
            method_id = file.split("%")[0]
            if method_ids is not None and method_id not in method_ids:
                continue
            file_paths.append(os.path.join(root, file))

    submits = 0
    total = len(file_paths) * test_number

    if multiprocess:
        logger.info("Multi process executing!")
        with concurrent.futures.ProcessPoolExecutor(max_workers=process_number) as executor:
            for idx, file_path in enumerate(file_paths):
                _, base_name = os.path.split(file_path.replace("/dataset/", "/result/"))
                base_dir = os.path.join(result_path, base_name.split(".json")[0])
                for test_num in range(1, test_number + 1):
                    submits += 1
                    executor.submit(whole_process, test_num, base_name, base_dir, repair, submits, total)
        logger.info("Main process executing!")
    else:
        logger.info("Single process executing!")
        for idx, file_path in enumerate(file_paths):
            _, base_name = os.path.split(file_path.replace("/dataset/", "/result/"))
            base_dir = os.path.join(result_path, base_name.split(".json")[0])
            for test_num in range(1, test_number + 1):
                submits += 1
                whole_process(test_num, base_name, base_dir, repair, submits, total)
