import os
import xml.etree.ElementTree as ET
import subprocess
import shutil

class PomModifier:
    def __init__(self, project_root):
        self.project_root = project_root
        self.pom_path = os.path.join(self.project_root, 'pom.xml')
        self.backup_pom_path = os.path.join(self.project_root, 'pom.xml.backup')

    def find_pom(self):
        if os.path.isfile(self.pom_path):
            print(f"Found pom.xml at {self.pom_path}")
            return True
        else:
            print("pom.xml not found in the root directory")
            return False

    def create_backup(self):
        if not os.path.exists(self.backup_pom_path):
            shutil.copy(self.pom_path, self.backup_pom_path)
            print(f"Backup of pom.xml created at {self.backup_pom_path}")
        else:
            print(f"A backup of pom.xml already exists at {self.backup_pom_path}")

    def restore_pom(self):
        if os.path.exists(self.backup_pom_path):
            shutil.copy(self.backup_pom_path, self.pom_path)
            print("pom.xml restored from backup.")
        else:
            print("No backup found to restore.")

    def strip_namespace(self, tree):
        for elem in tree.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]

    def check_and_add_dependencies(self):
        if not self.find_pom():
            return False
        self.create_backup()
        tree = ET.parse(self.pom_path)
        root = tree.getroot()
        self.strip_namespace(tree)

        dependencies_section = root.find('dependencies')

        if dependencies_section is None:
            dependencies_section = ET.SubElement(root, 'dependencies')

        dependencies = [dep.find('artifactId').text for dep in dependencies_section.findall('dependency')]

        junit_jupiter_api_found = 'junit-jupiter-api' in dependencies
        junit_jupiter_engine_found = 'junit-jupiter-engine' in dependencies

        changes_made = False

        if not junit_jupiter_api_found:
            print("Adding junit-jupiter-api to dependencies")
            self.add_dependency(dependencies_section, 'org.junit.jupiter', 'junit-jupiter-api', '5.7.0')
            changes_made = True

        if not junit_jupiter_engine_found:
            print("Adding junit-jupiter-engine to dependencies")
            self.add_dependency(dependencies_section, 'org.junit.jupiter', 'junit-jupiter-engine', '5.7.0')
            changes_made = True

        if changes_made:
            tree.write(self.pom_path, xml_declaration=True, encoding='utf-8')
            print("Updated pom.xml with missing dependencies.")
        else:
            print("No changes needed. Dependencies already present.")

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
        try:
            with subprocess.Popen(
                [r'mvn', 'dependency:resolve'],
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            ) as process:
                stdout, stderr = process.communicate()

            if process.returncode != 0:
                print(f"Error occurred during 'mvn dependency:resolve' with exit code {process.returncode}.")
                print(f"Error message: {stderr}")
                self.restore_pom()
            else:
                print("Maven dependency resolution successful.")
                print(stdout)

        except subprocess.SubprocessError as e:
            print(f"An exception occurred while running 'mvn dependency:resolve': {str(e)}")
            self.restore_pom()

    

    def main(project_root):
        modifier = PomModifier(project_root)
        if modifier.check_and_add_dependencies():
            modifier.run_maven_dependency_resolve()
        else:
            print("No need to run 'mvn dependency:resolve'.")
