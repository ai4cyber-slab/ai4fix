import os
import requests
import re
import time
from ai4test.ai4test_config import dep_config, refresh
from ai4test.find_replace_versions import get_mockito_and_junit_versions

DEPENDENCY_DIR = "/app/ai4test/dependencies/lib"
BASE_URL = "https://repo1.maven.org/maven2/"

def download_file(url, output_path):
    """Download a file from the given URL to the specified output path"""
    print(f"Downloading {url}...")
    response = requests.get(url)
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            f.write(response.content)
        return True
    else:
        print(f"Failed to download: {url}, Status code: {response.status_code}")
        return False

def extract_property_value(pom_content, property_name):
    """Extract property value from POM content"""
    pattern = "<{0}>([^<]+)</{0}>".format(property_name)
    match = re.search(pattern, pom_content)
    if match:
        return match.group(1)
    
    if not property_name.startswith("project."):
        return extract_property_value(pom_content, "project.{0}".format(property_name))
    
    return None

def get_dependency_version(group_id, artifact_id, mockito_version):
    """Get the correct version of a dependency from the Mockito POM file"""
    group_path = "org/mockito"
    pom_url = "{0}{1}/mockito-core/{2}/mockito-core-{2}.pom".format(BASE_URL, group_path, mockito_version)
    
    try:
        response = requests.get(pom_url)
        if response.status_code != 200:
            print("Failed to fetch POM: {0}".format(pom_url))
            return None
        
        pom_content = response.text
        
        pattern = '<dependency>\\s*<groupId>{0}</groupId>\\s*<artifactId>{1}</artifactId>\\s*<version>([^<]+)</version>'.format(
            re.escape(group_id), re.escape(artifact_id))
        version_match = re.search(pattern, pom_content)
        
        if version_match:
            version = version_match.group(1)
            if version.startswith("${") and version.endswith("}"):
                property_name = version[2:-1]
                return extract_property_value(pom_content, property_name)
            return version
        
        prop_pattern = '<dependency>\\s*<groupId>{0}</groupId>\\s*<artifactId>{1}</artifactId>\\s*<version>\\${{([^}}]+)}}</version>'.format(
            re.escape(group_id), re.escape(artifact_id))
        prop_match = re.search(prop_pattern, pom_content)
        
        if prop_match:
            property_name = prop_match.group(1)
            return extract_property_value(pom_content, property_name)
    
    except Exception as e:
        print("Error parsing POM for {0}:{1}: {2}".format(group_id, artifact_id, str(e)))
    
    print("Could not find version for {0}:{1} in Mockito {2}".format(group_id, artifact_id, mockito_version))
    return None

def download_mockito_dependencies():
    """Download Mockito and its required dependencies"""
    refresh()
    os.makedirs(DEPENDENCY_DIR, exist_ok=True)
    
    MOCKITO_VERSION = dep_config.get("DEFAULT", "MOCKITO_VERSION")
    dependencies = [
        {"group_id": "org.mockito", "artifact_id": "mockito-core", "version": MOCKITO_VERSION},
        {"group_id": "org.mockito", "artifact_id": "mockito-inline", "version": MOCKITO_VERSION},
        {"group_id": "org.mockito", "artifact_id": "mockito-junit-jupiter", "version": MOCKITO_VERSION},
        {"group_id": "net.bytebuddy", "artifact_id": "byte-buddy", "version": None},
        {"group_id": "net.bytebuddy", "artifact_id": "byte-buddy-agent", "version": None},
        {"group_id": "org.objenesis", "artifact_id": "objenesis", "version": None}
    ]
    
    for i, dep in enumerate(dependencies):
        if dep["version"] is None:
            dep["version"] = get_dependency_version(dep["group_id"], dep["artifact_id"], MOCKITO_VERSION)
            dependencies[i] = dep
    
    jar_paths = []
    for dep in dependencies:
        if dep["version"] is None:
            print("ERROR: Could not determine version for {0}:{1}".format(dep["group_id"], dep["artifact_id"]))
            print("Please specify this version manually in the script.")
            continue
        
        group_path = dep["group_id"].replace(".", "/")
        jar_url = "{0}{1}/{2}/{3}/{2}-{3}.jar".format(
            BASE_URL, group_path, dep["artifact_id"], dep["version"])
        jar_filename = "{0}-{1}-manual.jar".format(dep["artifact_id"], dep["version"])
        jar_path = os.path.join(DEPENDENCY_DIR, jar_filename)
        
        if os.path.exists(jar_path):
            print("Using existing: {0}".format(jar_path))
        else:
            success = download_file(jar_url, jar_path)
            if not success:
                print("ERROR: Failed to download {0}:{1}:{2}".format(
                    dep["group_id"], dep["artifact_id"], dep["version"]))
                continue
        
        jar_paths.append(jar_path)
    
    mockito_classpath = ":".join(jar_paths)
    
    update_mockito_jar_in_config(mockito_classpath, )

    return jar_paths


def remove_jar_files(jar_paths):
    """Remove the JAR files listed"""
    removed = []
    for path in jar_paths:
        if os.path.exists(path):
            os.remove(path)
            removed.append(path)


def update_mockito_jar_in_config(classpath_value, config_path="/app/config/dep_config.ini"):
    """Update or append MOCKITO_JAR in the config file"""
    lines = []
    found = False

    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            lines = f.readlines()

    lines = [line if line.endswith('\n') else line + '\n' for line in lines]

    for i, line in enumerate(lines):
        if line.startswith("MOCKITO_JAR"):
            lines[i] = f"MOCKITO_JAR={classpath_value}\n"
            found = True
            break

    if not found:
        lines.append(f"MOCKITO_JAR={classpath_value}\n")

    with open(config_path, "w") as f:
        f.writelines(lines)



def find_main_pom(project_path: str) -> str | None:
    """
    Returns the path to the main pom.xml in the root of the project directory.
    """
    pom_path = os.path.join(project_path, "pom.xml")
    return pom_path if os.path.isfile(pom_path) else None



if __name__ == "__main__":
    pom_path = find_main_pom(os.environ.get('PROJECT_PATH'))
    if pom_path:
        get_mockito_and_junit_versions(pom_path=pom_path)
        jar_paths = download_mockito_dependencies()
        time.sleep(10)
        remove_jar_files(jar_paths)
    else:
        print(f"pom.xml not found in project root {os.environ.get('PROJECT_PATH')}")