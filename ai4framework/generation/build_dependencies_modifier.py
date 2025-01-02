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

    def create_backup(self):
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
            logger.error("No backup found to restore.")

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
        return required_dependencies

    def check_and_add_dependencies(self, import_content):
        """
        Checks and adds dependencies based on the currently set build tool.
        For now, only Maven logic is implemented.
        """
        if self.build_tool == 'maven':
            return self.maven_check_and_add_dependencies(import_content)
        elif self.build_tool == 'gradle':
            # TODO: gradle later modify build.gradle or maybee settings.gradle
            logger.info("Gradle build tool detected.")
            return False
        else:
            logger.info(f"No known dependency update logic for build tool '{self.build_tool}'")
            return False

    def maven_check_and_add_dependencies(self, import_content):
        if not self.find_pom():
            return False
        self.create_backup()
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
            logger.debug(f"Adding dependency: {group_id}:{artifact_id}:{version}")
            self.add_dependency(dependencies_section, group_id, artifact_id, version)
            changes_made = True

        if changes_made:
            ET.indent(tree, space="    ", level=0)
            tree.write(self.pom_path, xml_declaration=True, encoding='utf-8')
            logger.debug("Updated pom.xml with missing dependencies.")
        else:
            logger.debug("No changes made to pom.xml.")

        return changes_made

    def add_dependency(self, dependencies_section, group_id, artifact_id, version):
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
                logger.error(f"Error occurred during 'mvn dependency:resolve' with exit code {process.returncode}.")
                logger.error(f"Error message: {stderr}")
                self.restore_pom()
            else:
                logger.debug("Maven dependency resolution successful.")
                logger.debug(stdout)

        except subprocess.SubprocessError as e:
            logger.debug(f"An exception occurred while running 'mvn dependency:resolve': {str(e)}")
            self.restore_pom()

    def process_java_file(self, java_file_path):
        if not os.path.isfile(java_file_path):
            logger.error(f"Java file not found at {java_file_path}")
            return False

        with open(java_file_path, 'r') as f:
            import_content = f.read()

        changes_made = self.check_and_add_dependencies(import_content)

        if self.build_tool == 'maven' and changes_made:
            self.run_maven_dependency_resolve()
        elif self.build_tool == 'gradle':
            # TODO: resolve gradle dependencies
            pass

        return True

    @staticmethod
    def main(project_root, java_file_path, dependencies_json_path, build_tool='maven'):
        modifier = BuildDependenciesModifier(project_root, dependencies_json_path, build_tool)
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
