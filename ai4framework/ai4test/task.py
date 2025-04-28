import subprocess
from ai4test.test_runner import TestRunner
from ai4test.class_parser import ClassParser
from ai4test.tools import *
from ai4test.ai4test_logger import logger
from ai4test.ai4test_config import ai4test_dir
import os

class Task:

    @staticmethod
    def test(test_path, target_path):
        """
        Run test task, make sure the target project has be compiled and installed.(run `mvn compile install`)
        """
        test_task = TestTask(test_path, target_path)
        return test_task.single_test()

    @staticmethod
    def all_test(test_path, target_path, source_files=[]):
        """
        Run test task, make sure the target project has be compiled and installed.(run `mvn compile install`)
        """
        test_task = TestTask(test_path, target_path)
        return test_task.all_test(source_files)

    @staticmethod
    def parse(target_path):
        """
        Run parse task, extract class information of target project.
        """
        parse_task = ParseTask()
        return parse_task.parse_project(target_path)


class TestTask:

    def __init__(self, test_path, target_path):
        self.test_path = test_path
        self.target_path = target_path
        self.runner = TestRunner(test_path, target_path)

        # define the threshold for CPU utilization and available memory
        self.cpu_threshold = 80
        self.mem_threshold = 1024 * 1024 * 5000  # 5G

    def single_test(self):
        """
        Only run tests.
        """
        if check_java_version() != 11:
            raise Exception("Wrong java version! Need: java 11")
        return self.runner.start_single_test()

    def all_test(self, source_files=[]):
        """
        Run all test cases.
        target_path: target project path
        """
        if check_java_version() != 11:
            raise Exception("Wrong java version! Need: java 11")
        return self.runner.start_all_test(source_files)


class ParseTask:

    def __init__(self):
        self.parser = ClassParser()
        self.output = os.path.join(ai4test_dir, 'class_info')

    def parse_project(self, target_path):
        """
        Analyze a single project
        """
        target_path = target_path.rstrip('/')
        os.makedirs(self.output, exist_ok=True)
        tot_m, output_path = self.find_classes(target_path)
        return output_path

    def find_classes(self, target_path):
        """
        Find all classes exclude tests
        Finds test cases using @Test annotation
        """
        # Run analysis
        logger.info(f"Parse {target_path} ...")
        if not os.path.exists(target_path):
            return 0, ""
        # Test Classes
        try:
            result = subprocess.check_output(r'grep -l -r @Test --include \*.java {}'.format(target_path), shell=True)
            tests = result.decode('ascii').splitlines()
        except:
            tests = []
        # Java Files
        try:
            result = subprocess.check_output(['find', target_path, '-name', '*.java'])
            java = result.decode('ascii').splitlines()
        except:
            return 0, ""
        # All Classes exclude tests
        focals = list(set(java) - set(tests))
        focals = [f for f in focals if not "src/test" in f]
        project_name = os.path.split(target_path)[1]
        output = os.path.join(self.output, project_name)
        os.makedirs(output, exist_ok=True)
        return self.parse_all_classes(focals, project_name, output), output

    def parse_all_classes(self, focals, project_name, output):
        classes = {}
        for focal in focals:
            parsed_classes = self.parser.parse_file(focal)
            for _class in parsed_classes:
                _class["project_name"] = project_name

            classes[focal] = parsed_classes
            json_path = os.path.join(output, os.path.split(focal)[1] + ".json")
            self.export_result(classes[focal], json_path)
        return classes

    @staticmethod
    def export_result(data, out):
        """
        Exports data as json file
        """
        directory = os.path.dirname(out)
        if not os.path.exists(directory):
            os.makedirs(directory)
        with open(out, "w") as text_file:
            data_json = json.dumps(data)
            text_file.write(data_json)

    def get_class_path(self, start_path, filename):
        for root, dirs, files in os.walk(start_path):
            if filename in files:
                return os.path.join(root, filename)
