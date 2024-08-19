import subprocess

def run_maven_spotbugs(maven_executable, project_root):
    result = subprocess.run(
        [maven_executable, 'spotbugs:spotbugs'],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    return result
