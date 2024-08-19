import subprocess

def run_maven_clean_test(maven_executable, project_root):
    result = subprocess.run(
        [maven_executable, 'clean', 'test'],
        cwd=project_root,
        capture_output=True,
        text=True
    )
    return result