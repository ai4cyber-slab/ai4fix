import os
import subprocess
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
from ai4test.ai4test_config import ai4test_dir


def generate_before_report(project_root, jacoco_agent_path, jacoco_cli_path):
    project_root = Path(project_root).resolve()
    ai4test_root = Path(ai4test_dir).resolve()
    report_dir = ai4test_root / "pre-reports"
    exec_file = report_dir / "jacoco-pre.exec"
    report_file = report_dir / "jacoco-pre.xml"

    os.makedirs(report_dir, exist_ok=True)

    print(f"[INFO] Project root: {project_root}")

    # Show what will be built
    print("[INFO] Showing modules to be built:")
    subprocess.run(["mvn", "-B", "validate"], cwd=project_root)

    print("[INFO] Cleaning project...")
    subprocess.run(["mvn", "clean"], cwd=project_root, check=True, stdout=subprocess.DEVNULL)

    print("[INFO] Running tests with JaCoCo agent (mvn test)...")
    env = os.environ.copy()
    env["MAVEN_OPTS"] = f"-javaagent:{jacoco_agent_path}=destfile={exec_file}"
    env["USER"] = ""  # to make Struts tests pass
    result = subprocess.run(["mvn", "test"], cwd=project_root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("[INFO] mvn test finished with exit code", result.returncode)
    if result.returncode != 0:
        print("[WARN] Some tests failed. Proceeding to generate report anyway.")
        print("[STDERR]", result.stderr.decode())

    print("[INFO] Finding class and source files...")
    classfiles = []
    sourcefiles = []
    for root, dirs, files in os.walk(project_root):
        path = Path(root)
        if path.match("*/target/classes"):
            print(f"[FOUND] Class directory: {root}")
            classfiles.append(str(path))
        if path.match("*/src/main/java"):
            print(f"[FOUND] Source directory: {root}")
            sourcefiles.append(str(path))

    if not classfiles or not sourcefiles:
        print("[ERROR] Could not find class or source files.")
        sys.exit(1)

    cmd = [
        "java", "-jar", str(jacoco_cli_path), "report", str(exec_file),
        *[f"--classfiles={c}" for c in classfiles],
        *[f"--sourcefiles={s}" for s in sourcefiles],
        f"--xml={report_file}"
    ]

    print("[INFO] Generating XML report...")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("[INFO] Jacoco CLI finished with exit code", result.returncode)
    if result.returncode != 0:
        print("[STDERR]", result.stderr.decode())
        sys.exit(result.returncode)


    print("[INFO] Post-processing report paths to be absolute...")
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

    print(f"[DONE] Final report available at {report_file}")
    return report_file, sourcefiles


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python generate_before_report.py <project_root> <jacoco_agent_path> <jacoco_cli_path>")
        sys.exit(1)

    generate_before_report(sys.argv[1], sys.argv[2], sys.argv[3])
