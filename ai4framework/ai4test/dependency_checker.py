import xml.etree.ElementTree as ET
import os
import sys

# List of important libraries
required_libraries = [
    {"groupId": "org.mockito", "artifactId": "mockito-core"},
    {"groupId": "org.mockito", "artifactId": "mockito-junit-jupiter"},
    {"groupId": "org.mockito", "artifactId": "mockito-inline"},
    {"groupId": "junit", "artifactId": "junit"},  # Only if version starts with 4
]

# JUnit 5 specific dependencies
junit5_libraries = [
    {"groupId": "org.junit.jupiter", "artifactId": "junit-jupiter-api"},
    {"groupId": "org.junit.jupiter", "artifactId": "junit-jupiter-engine"},
    {"groupId": "org.junit.jupiter", "artifactId": "junit-jupiter-params"},
    {"groupId": "org.junit.jupiter", "artifactId": "junit-jupiter"},
]

def parse_pom(pom_path):
    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}

        dependencies = []
        for dep in root.findall(".//m:dependency", ns):
            groupId = dep.find("m:groupId", ns)
            artifactId = dep.find("m:artifactId", ns)
            version = dep.find("m:version", ns)

            if groupId is not None and artifactId is not None:
                dependencies.append({
                    "groupId": groupId.text.strip(),
                    "artifactId": artifactId.text.strip(),
                    "version": version.text.strip() if version is not None else None
                })
        return dependencies
    except Exception as e:
        print(f"[ERROR] Failed to parse pom.xml: {e}")
        return []

def find_dependency(dependencies, group_id, artifact_id):
    for dep in dependencies:
        if dep["groupId"] == group_id and dep["artifactId"] == artifact_id:
            return dep
    return None

def print_missing_dependency_info(group_id, artifact_id, version):
    print(f"    ➔ To manually install it, run:")
    print(f"        mvn dependency:get -Dartifact={group_id}:{artifact_id}:{version}")
    print(f"    ➔ Then verify the files exist under:")
    print(f"        /root/.m2/repository/{group_id.replace('.', '/')}/{artifact_id}/{version}/")
    print(f"    ➔ Add this into your pom.xml inside <dependencies>:")
    print(f"""
    <dependency>
        <groupId>{group_id}</groupId>
        <artifactId>{artifact_id}</artifactId>
        <version>{version}</version>
        <scope>test</scope>
    </dependency>
    """.strip())

def generate_report(pom_path, expected_versions, output_file=None):
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            original_stdout = sys.stdout
            sys.stdout = f
            _generate(pom_path, expected_versions)
            sys.stdout = original_stdout
    else:
        _generate(pom_path, expected_versions)

def _generate(pom_path, expected_versions):
    print("Tests generated were tested with the following versions:\n")

    dependencies = parse_pom(pom_path)
    junit_version = expected_versions.get("junit", "")

    # Check normal dependencies, but skip junit-4 if junit 5 is expected
    for lib in required_libraries:
        artifact_id = lib["artifactId"]
        expected_version = expected_versions.get(artifact_id)

        if expected_version is None:
            print(f"[SKIP] No expected version given for {artifact_id}, skipping...")
            continue

        # If this is plain junit and we're on junit 5, skip it
        if artifact_id == "junit" and junit_version.startswith("5"):
            continue

        group_id = lib["groupId"]
        found = find_dependency(dependencies, group_id, artifact_id)

        print(f"- {artifact_id}: expected version {expected_version}")
        if found is None:
            print(f"  ➔ [MISSING] Not found in pom.xml.")
            print_missing_dependency_info(group_id, artifact_id, expected_version)
        else:
            actual_version = found["version"]
            if actual_version == expected_version:
                print(f"  ➔ [OK] Found version {actual_version}")
            else:
                print(f"  ➔ [WARN] Found version {actual_version}, but expected {expected_version}. It might still work.")

    # Handle JUnit 5 special case
    if junit_version.startswith("5"):
        print("\n[INFO] JUnit 5 detected. Checking required JUnit 5 components:")
        for lib in junit5_libraries:
            group_id = lib["groupId"]
            artifact_id = lib["artifactId"]
            expected_version = junit_version  # Same expected version for all

            found = find_dependency(dependencies, group_id, artifact_id)
            print(f"- {artifact_id}: expected version {expected_version}")
            if found is None:
                print(f"  ➔ [MISSING] Not found in pom.xml.")
                print_missing_dependency_info(group_id, artifact_id, expected_version)
            else:
                actual_version = found["version"]
                if actual_version == expected_version:
                    print(f"  ➔ [OK] Found version {actual_version}")
                else:
                    print(f"  ➔ [WARN] Found version {actual_version}, but expected {expected_version}. It might still work.")

    print("\nReminder: Ensure your pom.xml and local Maven repository are consistent for best results.")

if __name__ == "__main__":
    pom_path = "pom.xml"
    expected_versions = {
        "mockito-core": "3.12.4",
        "mockito-junit-jupiter": "3.12.4",
        "mockito-inline": "3.12.4",
        "junit": "5.10.2"
    }
    generate_report(pom_path, expected_versions, output_file="dependency_report.txt")
    print("[INFO] Dependency report written to dependency_report.txt")
