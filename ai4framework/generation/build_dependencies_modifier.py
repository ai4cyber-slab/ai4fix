import os
import json
import xml.etree.ElementTree as ET
import subprocess
import shutil
import re
from utils.logger import logger

class BuildDependenciesModifier:
    def __init__(self, project_root, testFilePath, dependencies_json_path, build_tool='maven'):
        self.project_root = project_root
        self.dependencies_json_path = dependencies_json_path
        self.build_tool = build_tool.lower()
        self.testFilePath = testFilePath


        self.pom_path = find_pom_in_hierarchy(testFilePath)
        self.pom_path = self.pom_path if self.pom_path else os.path.join(self.project_root, 'pom.xml')
        self.backup_pom_path = self.pom_path.replace('pom.xml', 'pom.xml.org')
        
        self.gradle_path = os.path.join(self.project_root, 'build.gradle')
        self.backup_gradle_path = os.path.join(self.project_root, 'build.gradle.org')

        self.import_to_dependency = self.load_dependencies_mapping()
        self.dependency_versions = self.load_dependency_versions()

    def load_dependencies_mapping(self):
        if not os.path.isfile(self.dependencies_json_path):
            logger.error(f"Dependencies JSON file not found at {self.dependencies_json_path}")
            return {}
        with open(self.dependencies_json_path, 'r') as f:
            try:
                data = json.load(f)
                logger.debug(f"Loaded dependencies mapping from {self.dependencies_json_path}")
                return data
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON file: {str(e)}")
                return {}

    def load_dependency_versions(self):
        return {
            ("junit", "junit"): "[4.13.2,)",
            ("org.junit.jupiter", "junit-jupiter-api"): "[5.8.1,)",
            ("org.junit.jupiter", "junit-jupiter-engine"): "[5.8.1,)",
            ("org.junit.jupiter", "junit-jupiter-params"): "[5.8.1,)",
            ("org.mockito", "mockito-core"): "[4.0.0,)",
            ("org.hamcrest", "hamcrest"): "[2.2,)",
            ("org.assertj", "assertj-core"): "[3.21.0,)",
            ("com.fasterxml.jackson.core", "jackson-databind"): "[2.13.0,)",
            ("org.apache.commons", "commons-lang3"): "[3.12.0,)",
            ("commons-io", "commons-io"): "[2.11.0,)",
            ("org.testng", "testng"): "[7.4.0,)",
            ("org.powermock", "powermock-module-junit4"): "[2.0.9,)",
            ("org.powermock", "powermock-api-mockito2"): "[2.0.9,)",
            ("org.easymock", "easymock"): "[4.3,)",
            ("com.github.stefanbirkner", "system-lambda"): "[1.2.0,)",
            ("com.google.guava", "guava"): "[31.0.1-jre,)",
            ("org.awaitility", "awaitility"): "[4.1.1,)",
            ("com.github.tomakehurst", "wiremock"): "[2.27.2,)",
            ("org.quicktheories", "quicktheories"): "[0.26,)",
            ("org.junit-pioneer", "junit-pioneer"): "[1.4.0,)",
            ("org.jmock", "jmock"): "[2.12.0,)",
            ("org.jmock", "jmock-junit4"): "[2.12.0,)",
            ("org.jmockit", "jmockit"): "[1.49,)",
            ("org.slf4j", "slf4j-api"): "[1.7.32,)",
            ("org.projectlombok", "lombok"): "[1.18.22,)",
            ("org.apache.logger.log4j", "log4j-api"): "[2.14.1,)",
            ("org.opentest4j", "opentest4j"): "[1.2.0,)"
        }

    def find_pom(self):
        if os.path.isfile(self.pom_path):
            logger.debug(f"Found pom.xml at {self.pom_path}")
            return True
        else:
            logger.error("pom.xml not found in the root directory")
            return False

    def create_backup_pom(self):
        if not os.path.exists(self.backup_pom_path):
            shutil.copy(self.pom_path, self.backup_pom_path)
            logger.debug(f"Backup of pom.xml created at {self.backup_pom_path}")
        else:
            logger.debug(f"A backup of pom.xml already exists at {self.backup_pom_path}")

    def restore_pom(self):
        if os.path.exists(self.backup_pom_path):
            shutil.copy(self.backup_pom_path, self.pom_path)
            logger.info("pom.xml restored from backup.")
        else:
            logger.error("No backup found to restore pom.xml.")

    def create_backup_gradle(self):
        if not os.path.exists(self.gradle_path):
            logger.warning(f"No build.gradle found at {self.gradle_path}. Creating an empty one.")
            with open(self.gradle_path, 'w') as f:
                f.write("plugins {\n    // e.g. id 'java'\n}\n\ndependencies {\n}\n")

        if not os.path.exists(self.backup_gradle_path):
            shutil.copy(self.gradle_path, self.backup_gradle_path)
            logger.debug(f"Backup of build.gradle created at {self.backup_gradle_path}")
        else:
            logger.debug(f"A backup of build.gradle already exists at {self.backup_gradle_path}")

    def restore_gradle(self):
        if os.path.exists(self.backup_gradle_path):
            shutil.copy(self.backup_gradle_path, self.gradle_path)
            logger.info("build.gradle restored from backup.")
        else:
            logger.error("No backup found to restore build.gradle.")

    def strip_namespace(self, tree):
        for elem in tree.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]

    def parse_imports_from_content(self, import_content):
        import_pattern = re.compile(r'^import\s+([\w\.]+);')
        imports = set()
        for line in import_content.splitlines():
            line = line.strip()
            match = import_pattern.match(line)
            if match:
                imports.add(match.group(1))
        logger.debug(f"Parsed {len(imports)} unique imports from provided content.")
        return imports

    def collect_required_dependencies_from_imports(self, import_content):
        all_imports = self.parse_imports_from_content(import_content)
        required_dependencies = set()

        for fqcn in all_imports:
            if fqcn in self.import_to_dependency:
                dep_info = self.import_to_dependency[fqcn]
                group_id = dep_info['groupId']
                artifact_id = dep_info['artifactId']
                required_dependencies.add((group_id, artifact_id))
            else:
                logger.debug(f"No dependency mapping found for import: {fqcn}")

        logger.debug(f"Total dependencies required based on imports: {len(required_dependencies)}")

        # ensure the engine is also included.
        if ("org.junit.jupiter", "junit-jupiter-api") in required_dependencies:
            required_dependencies.add(("org.junit.jupiter", "junit-jupiter-engine"))

        return required_dependencies

    def check_and_add_dependencies(self, import_content):
        """
        Checks and adds dependencies based on the currently set build tool.
        """
        if self.build_tool == 'maven':
            return self.maven_check_and_add_dependencies(import_content)
        elif self.build_tool == 'gradle':
            return self.gradle_check_and_add_dependencies(import_content)
        else:
            logger.info(f"No known dependency update logic for build tool '{self.build_tool}'")
            return False

    #########################
    # Maven-specific methods
    #########################

    def maven_check_and_add_dependencies(self, import_content):
        if not self.find_pom():
            return False

        self.create_backup_pom()
        tree = ET.parse(self.pom_path)
        root = tree.getroot()
        self.strip_namespace(tree)

        dependencies_section = root.find('dependencies')

        if dependencies_section is None:
            dependencies_section = ET.SubElement(root, 'dependencies')

        existing_dependencies = set()
        for dep in dependencies_section.findall('dependency'):
            group_id = dep.find('groupId').text if dep.find('groupId') is not None else ""
            artifact_id = dep.find('artifactId').text if dep.find('artifactId') is not None else ""
            existing_dependencies.add((group_id, artifact_id))

        required_dependencies = self.collect_required_dependencies_from_imports(import_content)
        missing_dependencies = required_dependencies - existing_dependencies

        if not missing_dependencies:
            logger.debug("No changes needed. All required dependencies are already present.")
            return False

        changes_made = False
        for group_id, artifact_id in missing_dependencies:
            version = self.dependency_versions.get((group_id, artifact_id), "LATEST")
            logger.debug(f"Adding Maven dependency: {group_id}:{artifact_id}:{version}")
            self.add_maven_dependency(dependencies_section, group_id, artifact_id, version)
            changes_made = True

        if changes_made:
            try:
                ET.indent(tree, space="    ", level=0)
            except AttributeError:
                logger.debug("Failed to indent XML tree. This may not be supported due to Python version use >=3.9")
            tree.write(self.pom_path, xml_declaration=True, encoding='utf-8')
            logger.debug("Updated pom.xml with missing dependencies.")

        return changes_made

    def add_maven_dependency(self, dependencies_section, group_id, artifact_id, version):
        dependency = ET.SubElement(dependencies_section, 'dependency')
        group_elem = ET.SubElement(dependency, 'groupId')
        group_elem.text = group_id

        artifact_elem = ET.SubElement(dependency, 'artifactId')
        artifact_elem.text = artifact_id

        version_elem = ET.SubElement(dependency, 'version')
        version_elem.text = version

    def run_maven_dependency_resolve(self):
        maven_executable = 'mvn'
        try:
            result = subprocess.run([maven_executable, '--version'], capture_output=True, text=True)
            if result.returncode != 0:
                logger.error("Maven is not installed or not in PATH")
                self.restore_pom()
                return
            logger.debug(f"Found Maven: {result.stdout.splitlines()[0]}")
        except FileNotFoundError:
            logger.error("Maven executable not found in PATH")
            self.restore_pom()
            return

        try:
            with subprocess.Popen(
                [maven_executable, 'dependency:resolve'],
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            ) as process:
                stdout, stderr = process.communicate()

            if process.returncode != 0:
                logger.error(
                    f"Error occurred during 'mvn dependency:resolve' "
                    f"with exit code {process.returncode}."
                )
                logger.error(f"Error message: {stderr}")
                self.restore_pom()
            else:
                logger.debug("Maven dependency resolution successful.")
                logger.debug(stdout)

        except subprocess.SubprocessError as e:
            logger.debug(f"An exception occurred while running 'mvn dependency:resolve': {str(e)}")
            self.restore_pom()

    #########################
    # Gradle-specific methods
    #########################

    def gradle_check_and_add_dependencies(self, import_content):
        self.create_backup_gradle()

        with open(self.gradle_path, 'r') as f:
            gradle_lines = f.readlines()

        existing_dependencies = self.parse_existing_gradle_dependencies(gradle_lines)
        required_dependencies = self.collect_required_dependencies_from_imports(import_content)
        missing_dependencies = required_dependencies - existing_dependencies

        if not missing_dependencies:
            logger.debug("No changes needed. All required dependencies are already present in build.gradle.")
            return False

        changes_made = self.add_missing_gradle_dependencies(gradle_lines, missing_dependencies)

        if changes_made:
            with open(self.gradle_path, 'w') as f:
                f.writelines(gradle_lines)

            logger.debug("Updated build.gradle with missing dependencies.")
            with open(self.gradle_path, 'r') as f:
                print(f.read())

        return changes_made

    def parse_existing_gradle_dependencies(self, gradle_lines):
        existing = set()
        pattern = re.compile(
            r'^\s*(?:testImplementation|implementation|compileOnly|runtimeOnly|testRuntimeOnly)\s+["\']([^:"\']+):([^:"\']+):[^:"\']+["\']'
        )

        for line in gradle_lines:
            match = pattern.search(line.strip())
            if match:
                group_id = match.group(1)
                artifact_id = match.group(2)
                existing.add((group_id, artifact_id))

        logger.debug(f"Found {len(existing)} existing Gradle dependencies.")
        return existing

    def add_missing_gradle_dependencies(self, gradle_lines, missing_dependencies):
        """
        Insert lines like:
            testImplementation 'groupId:artifactId:version'
        into the dependencies block. If no dependencies block is found, we create one.
        """
        changes_made = False


        def parse_version_range(v):
            try:
                if v.startswith('['):
                    v = v[1:]
                    if ',' in v:
                        v = v.split(',', 1)[0]
                    v = v.replace(')', '').replace(']', '')
                return v.strip()
            except Exception as e:
                logger.error(f"Error parsing version range: {str(e)}")
                return "latest.release"


        if not any('dependencies {' in line for line in gradle_lines):
            gradle_lines.append("\ndependencies {\n}\n")


        dep_block_start = None
        brace_depth = 0
        for i, line in enumerate(gradle_lines):
            if 'dependencies {' in line:
                dep_block_start = i
                break

        if dep_block_start is None:
            logger.error("Could not find or create dependencies block in build.gradle.")
            return False


        insertion_index = None
        found_open_brace = False
        for i in range(dep_block_start, len(gradle_lines)):
            if '{' in gradle_lines[i]:
                brace_depth += gradle_lines[i].count('{')
                found_open_brace = True
            if '}' in gradle_lines[i] and found_open_brace:
                brace_depth -= gradle_lines[i].count('}')
                if brace_depth == 0:
                    insertion_index = i
                    break

        if insertion_index is None:
            logger.error("Could not find closing brace for dependencies block in build.gradle.")
            return False


        new_lines = []
        for group_id, artifact_id in missing_dependencies:
            raw_version = self.dependency_versions.get((group_id, artifact_id), "latest.release")
            version = parse_version_range(raw_version)
            dep_line = f"    testImplementation '{group_id}:{artifact_id}:{version}'\n"
            new_lines.append(dep_line)

        gradle_lines[insertion_index:insertion_index] = new_lines
        changes_made = True

        return changes_made

    def run_gradle_dependency_resolve(self):
        gradle_executable = 'gradle'
        try:
            result = subprocess.run([gradle_executable, '--version'], capture_output=True, text=True)
            if result.returncode != 0:
                logger.error("Gradle is not installed or not in PATH")
                self.restore_gradle()
                return
            logger.debug(f"Found Gradle: {result.stdout.splitlines()[0]}")
        except FileNotFoundError:
            logger.error("Gradle executable not found in PATH")
            self.restore_gradle()
            return

        try:
            with subprocess.Popen(
                [gradle_executable, 'dependencies'],
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            ) as process:
                stdout, stderr = process.communicate()

            if process.returncode != 0:
                logger.error(
                    f"Error occurred during 'gradle dependencies' "
                    f"with exit code {process.returncode}."
                )
                logger.error(f"Error message: {stderr}")
                self.restore_gradle()
            else:
                logger.debug("Gradle dependencies resolution successful.")
                logger.debug(stdout)
        except subprocess.SubprocessError as e:
            logger.debug(f"An exception occurred while running 'gradle dependencies': {str(e)}")
            self.restore_gradle()

    #########################
    # Public method to process a Java file
    #########################

    def process_java_file(self, java_file_path):
        if not os.path.isfile(java_file_path):
            logger.error(f"Java file not found at {java_file_path}")
            return False

        with open(java_file_path, 'r') as f:
            import_content = f.read()

        changes_made = self.check_and_add_dependencies(import_content)

        # If changes were made, attempt to resolve
        if self.build_tool == 'maven' and changes_made:
            self.run_maven_dependency_resolve()
        elif self.build_tool == 'gradle' and changes_made:
            self.run_gradle_dependency_resolve()

        return True

    @staticmethod
    def main(project_root, java_file_path, dependencies_json_path, build_tool='maven'):
        modifier = BuildDependenciesModifier(project_root, java_file_path, dependencies_json_path, build_tool)
        return modifier.process_java_file(java_file_path)





################################
# Helper functions
# ##############################


def find_pom_in_hierarchy(test_file_path):
    """
    Traverse up the directory structure to find the nearest pom.xml and determine its type.
    """
    current_dir = os.path.dirname(os.path.abspath(test_file_path))
    while current_dir != os.path.dirname(current_dir):  # Stop at root
        pom_path = os.path.join(current_dir, 'pom.xml')
        if os.path.isfile(pom_path):
            # if is_multimodule_pom(pom_path):
            #     logger.debug(f"Multi-module pom.xml found at: {pom_path}")
            # else:
            #     logger.debug(f"Single-module pom.xml found at: {pom_path}")
            return pom_path
        current_dir = os.path.dirname(current_dir)
    return None

def is_multimodule_pom(pom_path):
    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()
        for elem in root.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]
        return root.find('modules') is not None
    except ET.ParseError:
        return False
