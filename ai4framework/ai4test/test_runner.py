import glob
import os
import subprocess
import re
from datetime import datetime
from ai4test.ai4test_config import (
    test_number,
    JUNIT_JAR,
    MOCKITO_JAR,
    LOG4J_JAR,
    JACOCO_AGENT,
    JACOCO_CLI,
    ai4test_dir,
    TIMEOUT,
)
import xml.etree.ElementTree as ET
from pathlib import Path
from ai4test.cover2cover import jacoco2cobertura
from ai4test.relocate import SmartTestRelocator


class TestRunner:
    def __init__(self, test_path, target_path, tool="jacoco"):
        self.coverage_tool = tool
        self.test_path = test_path
        self.target_path = target_path

        # Pre‑process
        self.dependencies = self.make_dependency()
        self.build_dir_name = "target/classes"
        self.build_dir = self.process_single_repo()

        self.COMPILE_ERROR = 0
        self.TEST_RUN_ERROR = 0

    def start_single_test(self):
        """Run a single‑method test case located under <test_path>/temp."""
        temp_dir = os.path.join(self.test_path, "temp")
        compiled_test_dir = os.path.join(self.test_path, "runtemp")
        os.makedirs(compiled_test_dir, exist_ok=True)
        try:
            test_file = os.path.abspath(glob.glob(temp_dir + "/*.java")[0])
            compiler_output = os.path.join(temp_dir, "compile_error")
            test_output = os.path.join(temp_dir, "runtime_error")
            success, exec_path = self.run_single_test(
                test_file, compiled_test_dir, compiler_output, test_output
            )
            if not success:
                return False
            else:
                self.report(
                    compiled_test_dir,
                    temp_dir,
                    exec_file=exec_path,
                )
        except Exception as e:
            print(e)
            return False
        return True

    def start_all_test(self, source_files=[]):
        """Collect all tests and run them."""
        date = datetime.now().strftime("%Y%m%d%H%M%S")
        tests_dir = os.path.join(ai4test_dir, f"tests%{date}")
        compiler_output_dir = os.path.join(tests_dir, "compiler_output")
        test_output_dir = os.path.join(tests_dir, "test_output")
        report_dir = os.path.join(tests_dir, "report")

        compiler_output = os.path.join(compiler_output_dir, "CompilerOutput")
        test_output = os.path.join(test_output_dir, "TestOutput")
        compiled_test_dir = os.path.join(tests_dir, "compiled_tests")

        self.copy_tests(tests_dir, source_files)

        rs = self.run_all_tests(
            tests_dir,
            compiled_test_dir,
            compiler_output,
            test_output,
            report_dir,
            source_files,
        )

        # 2. move passing tests to org project correct path and skip tests that didn't pass.
        skip_folder_runtime_error = os.path.join(tests_dir, "test_output")
        skip_folder_compile_error = os.path.join(tests_dir, "compiler_output")

        relocator = SmartTestRelocator(
            skip_folder_runtime_error, skip_folder_compile_error
        )
        relocator.relocate_tests(os.path.join(tests_dir, "test_cases"))
        return rs

    def run_all_tests(
        self,
        tests_dir,
        compiled_test_dir,
        compiler_output,
        test_output,
        report_dir,
        source_files=[],
    ):
        tests = os.path.join(tests_dir, "test_cases")
        total_compile = 0
        total_test_run = 0
        for t in range(1, 1 + test_number):
            print("Processing attempt:", t)
            exec_files = []  # collect .exec paths for this attempt
            for test_case_file in os.listdir(tests):
                if str(t) != test_case_file.split("_")[-1].replace("Test.java", ""):
                    continue
                total_compile += 1
                try:
                    test_file = os.path.join(tests, test_case_file)
                    success, exec_path = self.run_single_test(
                        test_file, compiled_test_dir, compiler_output, test_output
                    )
                    if success and exec_path:
                        exec_files.append(exec_path)
                except Exception as e:
                    print(e)

            # merge all exec files generated in this attempt
            if exec_files:
                merge_target = os.path.join(
                    compiled_test_dir, f"jacoco-merged-{t}.exec"
                )
                subprocess.run(
                    ["java", "-jar", JACOCO_CLI, "merge", *exec_files, "--destfile", merge_target],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                post_report = self.report(
                    compiled_test_dir,
                    os.path.join(report_dir, str(t)),
                    source_files,
                    exec_file=merge_target,
                )
            else:
                post_report = None

            total_test_run = total_compile - self.COMPILE_ERROR
            print("COMPILE TOTAL COUNT:", total_compile)
            print("COMPILE ERROR COUNT:", self.COMPILE_ERROR)
            print("TEST RUN TOTAL COUNT:", total_test_run)
            print("TEST RUN ERROR COUNT:", self.TEST_RUN_ERROR, "\n")
        return total_compile, total_test_run, post_report

    def run_single_test(
        self, test_file, compiled_test_dir, compiler_output, test_output
    ):
        """Compile and run a single test file.

        Returns
        -------
        (bool, str or None)
            success flag and path to the generated .exec file (if any)
        """
        # compile
        if not self.compile(test_file, compiled_test_dir, compiler_output):
            return False, None

        # unique exec file per test
        exec_path = os.path.join(
            compiled_test_dir, f"{os.path.basename(test_file)}.exec"
        )

        # runtime output file naming
        if os.path.basename(test_output) == "runtime_error":
            test_output_file = f"{test_output}.txt"
        else:
            test_output_file = f"{test_output}-{os.path.basename(test_file)}.txt"

        # build command
        cmd = self.java_cmd(compiled_test_dir, test_file, exec_path)

        # run
        try:
            result = subprocess.run(
                cmd,
                timeout=TIMEOUT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if result.returncode != 0:
                self.TEST_RUN_ERROR += 1
                self.export_runtime_output(result, test_output_file)
                return False, None
        except subprocess.TimeoutExpired:
            return False, None
        return True, exec_path

    @staticmethod
    def export_runtime_output(result, test_output_file):
        with open(test_output_file, "w") as f:
            f.write(result.stdout)
            error_msg = re.sub(r"log4j:WARN.*\n?", "", result.stderr)
            if error_msg:
                f.write(error_msg)

    def compile(self, test_file, compiled_test_dir, compiler_output):
        os.makedirs(compiled_test_dir, exist_ok=True)
        cmd = self.javac_cmd(compiled_test_dir, test_file)
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode != 0:
            self.COMPILE_ERROR += 1
            if os.path.basename(compiler_output) == "compile_error":
                compiler_output_file = f"{compiler_output}.txt"
            else:
                compiler_output_file = (
                    f"{compiler_output}-{os.path.basename(test_file)}.txt"
                )
            with open(compiler_output_file, "w") as f:
                f.write(result.stdout)
                f.write(result.stderr)
            return False
        return True

    def process_single_repo(self):
        if self.has_submodule(self.target_path):
            modules = self.get_submodule(self.target_path)
            postfixed = [f"{self.target_path}/{m}/{self.build_dir_name}" for m in modules]
            return ":".join(postfixed)
        return os.path.join(self.target_path, self.build_dir_name)

    @staticmethod
    def get_package(test_file):
        with open(test_file, "r") as f:
            return f.readline().strip().replace("package ", "").replace(";", "")

    # module detection helpers
    @staticmethod
    def is_module(project_path):
        return (
            os.path.isdir(project_path)
            and "pom.xml" in os.listdir(project_path)
            and "target" in os.listdir(project_path)
        )

    def get_submodule(self, project_path):
        return [
            d for d in os.listdir(project_path) if self.is_module(os.path.join(project_path, d))
        ]

    def has_submodule(self, project_path):
        return any(
            self.is_module(os.path.join(project_path, d))
            for d in os.listdir(project_path)
        )

    def javac_cmd(self, compiled_test_dir, test_file):
        classpath = (
            f"{JUNIT_JAR}:{MOCKITO_JAR}:{LOG4J_JAR}:"
            f"{self.dependencies}:{self.build_dir}:."
        )
        return [
            "javac",
            "-d",
            compiled_test_dir,
            "-classpath",
            classpath,
            test_file,
        ]

    def java_cmd(self, compiled_test_dir, test_file, exec_path=None):
        full_test_name = self.get_full_name(test_file)
        classpath = (
            f"{compiled_test_dir}/instrumented:{compiled_test_dir}:"
            f"{JUNIT_JAR}:{MOCKITO_JAR}:{LOG4J_JAR}:"
            f"{self.dependencies}:{self.build_dir}:."
        )

        if exec_path is None:
            exec_path = f"{compiled_test_dir}/jacoco.exec"

        if self.coverage_tool == "jacoco":
            return [
                "java",
                f"-javaagent:{JACOCO_AGENT}=destfile={exec_path}",
                "-classpath",
                classpath,
                "org.junit.platform.console.ConsoleLauncher",
                "--disable-banner",
                "--disable-ansi-colors",
                "--fail-if-no-tests",
                "--details=none",
                "--select-class",
                full_test_name,
            ]

    def get_full_name(self, test_file):
        package = self.get_package(test_file)
        test_case = os.path.splitext(os.path.basename(test_file))[0]
        return f"{package}.{test_case}" if package else test_case

    def report(self, datafile_dir, report_dir, source_files=[], exec_file=None):
        os.makedirs(report_dir, exist_ok=True)
        if self.coverage_tool == "jacoco":
            if exec_file is None:
                exec_file = f"{datafile_dir}/jacoco.exec"

            classfiles = []
            report_p = os.path.join(report_dir, "coverage.xml")
            for build in self.build_dir.split(":"):
                if os.path.isdir(build):
                    classfiles += ["--classfiles", build]
            result = subprocess.run(
                [
                    "java",
                    "-jar",
                    JACOCO_CLI,
                    "report",
                    exec_file,
                ]
                + classfiles
                + ["--xml", report_p],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            print(result.stdout + result.stderr)  # TODO: include in log file instead of just printing
            return self.filenames_to_absolute(report_p, source_files)

    def make_dependency(self):
        mvn_dependency_dir = "target/dependency"
        if not self.has_made():
            subprocess.run(
                f"mvn dependency:copy-dependencies -DoutputDirectory={mvn_dependency_dir} -f {self.target_path}/pom.xml",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                f"mvn install -DskipTests -f {self.target_path}/pom.xml",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        dep_jars = glob.glob(self.target_path + "/**/*.jar", recursive=True)
        return ":".join(set(dep_jars))

    def has_made(self):
        for dirpath, dirnames, filenames in os.walk(self.target_path):
            if "pom.xml" in filenames and "target" in dirnames:
                if "dependency" in os.listdir(os.path.join(dirpath, "target")):
                    return True
        return False

    def copy_tests(self, target_dir, source_files=[]):
        tests = glob.glob(self.test_path + "/**/*Test.java", recursive=True)
        target_project = os.path.basename(self.target_path.rstrip("/"))
        for sub in ("test_cases", "compiler_output", "test_output", "report"):
            os.makedirs(os.path.join(target_dir, sub), exist_ok=True)
        print("Copying tests to", target_project, "…")
        for tc in tests:
            tc_project = tc.split("/")[-4].split("%")[1]
            if tc_project == target_project and os.path.exists(self.target_path):
                os.system(f"cp {tc} {os.path.join(target_dir, 'test_cases')}")

    def filenames_to_absolute(self, report_file, sourcefiles=[]):
        if len(sourcefiles) == 0:
            return
        print("[INFO] Post-processing report paths to be absolute…")
        tree = ET.parse(report_file)
        root = tree.getroot()
        unresolved = []
        count_updated = 0

        for package in root.findall(".//package"):
            pkg_path = Path(package.get("name"))  # e.g., org/apache/tiles/web/util

            for clazz in package.findall("class"):
                filename = clazz.get("sourcefilename")  # e.g., TilesDispatchServlet.java
                rel_path = pkg_path / filename  # e.g., org/apache/tiles/web/util/TilesDispatchServlet.java
                resolved = False

                for src in sourcefiles:
                    full_path = Path(src) / rel_path
                    if full_path.exists():
                        abs_path = str(full_path.resolve())
                        print(f"[UPDATE] {rel_path} → {abs_path}")
                        clazz.set("sourcefilename", abs_path)
                        count_updated += 1
                        resolved = True
                        break

                if not resolved:
                    unresolved.append(str(rel_path))

        tree.write(report_file, encoding="utf-8", xml_declaration=True)

        print(f"[INFO] {count_updated} file paths updated to absolute.")
        if unresolved:
            print(f"[WARN] Could not resolve {len(unresolved)} classes:")
            for path in unresolved:
                print(f"  - {path}")
        cobertura_report_path = jacoco2cobertura(filename=report_file, state="post")
        return cobertura_report_path