import os
import subprocess


def switch_java_version(version):
    """Switch Java versions using the provided switch-java script."""
    try:
        script_path = os.path.join(os.sep, 'usr', 'local', 'bin', 'switch-java')
        result = subprocess.run(f"bash -c 'source {script_path} {version}'", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        raise Exception(f"Failed to switch Java version: {str(e)}")