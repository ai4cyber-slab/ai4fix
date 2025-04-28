import xml.etree.ElementTree as ET
import re
import os

def get_version_from_dependency(dependency, properties):
    version = dependency.findtext("version")
    if version and version.startswith("${") and version.endswith("}"):
        prop_key = version[2:-1]
        return properties.get(prop_key)
    return version

def extract_properties(root):
    properties = {}
    props = root.find("properties")
    if props is not None:
        for child in props:
            properties[child.tag] = child.text
    return properties

def extract_dependency_versions(root, properties):
    versions = {"mockito": None, "junit": None}

    def check_and_set(dep):
        group_id = dep.findtext("groupId")
        artifact_id = dep.findtext("artifactId")
        version = get_version_from_dependency(dep, properties)

        if group_id and artifact_id:
            gid = group_id.strip().lower()
            aid = artifact_id.strip().lower()

            if gid == "org.mockito" and not versions["mockito"]:
                versions["mockito"] = version
            elif gid == "org.junit.jupiter" and not versions["junit"]:
                versions["junit"] = version
            elif gid == "junit" and aid == "junit" and not versions["junit"]:
                versions["junit"] = version

    for section_tag in ["dependencies", "dependencyManagement/dependencies"]:
        section = root.find(section_tag)
        if section is not None:
            for dep in section.findall("dependency"):
                check_and_set(dep)

    return versions

def get_mockito_and_junit_versions(pom_path):
    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()

        # Strip namespaces
        for elem in root.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]

        properties = extract_properties(root)
        versions = extract_dependency_versions(root, properties)
        
        if versions:
            if "mockito" not in versions or not versions["mockito"]:
                versions["mockito"] = "3.12.4"
            if "junit" not in versions or not versions["junit"]:
                versions["junit"] = "4.13.2"

            print(versions)
            update_versions_in_config(versions["mockito"], versions["junit"])

        return versions
    except Exception as e:
        print("Error parsing POM:", str(e))
        return None

def update_versions_in_config(mockito_version, junit_version, config_path="/app/config/dep_config.ini"):
    lines = []
    found_mockito = False
    found_junit = False

    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            lines = f.readlines()

    # Clean lines to ensure each ends with '\n'
    lines = [line if line.endswith('\n') else line + '\n' for line in lines]

    for i, line in enumerate(lines):
        if line.startswith("MOCKITO_VERSION="):
            lines[i] = f"MOCKITO_VERSION={mockito_version}\n"
            found_mockito = True
        elif line.startswith("JUNIT_VERSION="):
            lines[i] = f"JUNIT_VERSION={junit_version}\n"
            found_junit = True

    if not found_mockito:
        lines.append(f"MOCKITO_VERSION={mockito_version}\n")
    if not found_junit:
        lines.append(f"JUNIT_VERSION={junit_version}\n")

    with open(config_path, "w") as f:
        f.writelines(lines)


if __name__ == "__main__":
    pom_file = "/app/pelo-project/pom.xml"
    versions = get_mockito_and_junit_versions(pom_file)
    if versions:
        print("Mockito version:", versions["mockito"])
        print("JUnit version:", versions["junit"])
