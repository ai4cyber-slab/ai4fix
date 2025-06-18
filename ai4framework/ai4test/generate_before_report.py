import os
import subprocess
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
from ai4test.ai4test_config import ai4test_dir
from utils.switcher import switch_java_version


def generate_before_report(project_root, jacoco_agent_path, jacoco_cli_path, config=None):
    # -------------------------------------------------------------------------
    # 1) Setup paths & configuration
    # -------------------------------------------------------------------------
    project_root   = Path(project_root).resolve()
    ai4test_root   = Path(ai4test_dir).resolve()
    report_dir     = ai4test_root / "pre-reports"
    exec_file      = report_dir / "jacoco-pre.exec"
    report_file    = report_dir / "jacoco-pre.xml"

    build_mode = (config.get("DEFAULT", "config.build_mode", fallback="online")
                        .strip().lower()) if config else "online"
    jdk_build_version = str(config.get("DEFAULT", "config.jdk_compiler_version", fallback="11"))

    report_dir.mkdir(parents=True, exist_ok=True)          # make sure both dirs exist
    exec_file.touch(exist_ok=True)                         # placeholder lets agent create file

    # -------------------------------------------------------------------------
    # 2) Clean project and switch to the compiler JVM
    # -------------------------------------------------------------------------
    print(f"[INFO] Project root: {project_root}")
    print("[INFO] Cleaning project ...")
    subprocess.run(["mvn", "clean", "-q"], cwd=project_root, check=True)

    switch_java_version(jdk_build_version)

    # -------------------------------------------------------------------------
    # 3) Build / test with *universal* JaCoCo agent injection
    # -------------------------------------------------------------------------
    agent_flag = f"-javaagent:{jacoco_agent_path}=destfile={exec_file},append=false"
    maven_props = [
        f"-DargLine={agent_flag}",          # vanilla surefire/failsafe
        f"-Djacoco.argLine={agent_flag}",   # pom.xml prepared by jacoco-maven-plugin
        f"-Dfailsafe.argLine={agent_flag}", # integration-test argLine (from 3.0.0-M5)
    ]

    threads = f"-T{os.cpu_count() or 1}"
    common_flags = [
        "install",                          # use 'test' if you don't need packaging
        "-DskipTests=false",
        "-Dmaven.test.failure.ignore=true",
        "-Dgpg.skip=true",
        "-Dmaven.javadoc.skip=true",
        threads,
        *maven_props,
    ]

    command = (["mvn", "-o"] if build_mode == "offline" else ["mvn"]) + common_flags
    print("[INFO] Launching Maven build with JaCoCo agent ...")
    result = subprocess.run(command, cwd=project_root)
    print("[INFO] mvn finished with exit code", result.returncode)
    if result.returncode != 0:
        print("[WARN] Build or tests failed – continuing to generate report.")

    # -------------------------------------------------------------------------
    # 4) Locate class / source roots
    # -------------------------------------------------------------------------
    print("[INFO] Scanning for class and source directories ...")
    classfiles, sourcefiles = [], []
    for root, _, _ in os.walk(project_root):
        path = Path(root).as_posix()
        if path.endswith("/target/classes"):
            print(f"[FOUND] Class dir  : {root}")
            classfiles.append(root)
        elif path.endswith("/src/main/java"):
            print(f"[FOUND] Source dir : {root}")
            sourcefiles.append(root)

    if not classfiles or not sourcefiles:
        sys.exit("[ERROR] No classfiles or sourcefiles found – aborting.")

    # -------------------------------------------------------------------------
    # 5) Generate XML report with JaCoCo CLI
    # -------------------------------------------------------------------------
    switch_java_version("11")                              # cli still runs fine on 11
    cli_cmd = [
        "java", "-jar", str(jacoco_cli_path), "report", str(exec_file),
        *[f"--classfiles={c}" for c in classfiles],
        *[f"--sourcefiles={s}" for s in sourcefiles],
        f"--xml={report_file}",
    ]

    print("[INFO] Generating XML report ...")
    result = subprocess.run(cli_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        print("[STDERR]", result.stderr.decode())
        sys.exit(result.returncode)
    print("[INFO] JaCoCo CLI finished successfully.")

    # -------------------------------------------------------------------------
    # 6) Make <sourcefilename> paths absolute (helps IDEs & CI viewers)
    # -------------------------------------------------------------------------
    print("[INFO] Rewriting paths inside XML ...")
    tree  = ET.parse(report_file)
    root_ = tree.getroot()
    unresolved, updated = [], 0

    for package in root_.findall(".//package"):
        pkg_rel_path = Path(package.get("name").replace(".", "/"))
        for clazz in package.findall("class"):
            filename = clazz.get("sourcefilename")
            candidate = pkg_rel_path / filename
            for src_root in sourcefiles:
                full = Path(src_root) / candidate
                if full.exists():
                    clazz.set("sourcefilename", str(full.resolve()))
                    updated += 1
                    break
            else:
                unresolved.append(str(candidate))

    tree.write(report_file, encoding="utf-8", xml_declaration=True)
    print(f"[INFO] Updated {updated} source paths.")
    if unresolved:
        print("[WARN] Unresolved sources:", *unresolved, sep="\n  - ")

    print(f"[DONE] Coverage XML report ready: {report_file}")
    return report_file, sourcefiles


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python generate_before_report.py <project_root> <jacoco_agent_jar> <jacoco_cli_jar>")
        sys.exit(1)

    generate_before_report(sys.argv[1], sys.argv[2], sys.argv[3])