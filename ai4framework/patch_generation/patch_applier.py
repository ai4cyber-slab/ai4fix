import json
import os
import subprocess
from typing import Dict, List
from configparser import ConfigParser

class PatchApplier:
    """
    A class to read patches from a JSON configuration and apply them.
    """

    def __init__(self, config: ConfigParser):
        """
        Initialize the applier with the path to the JSON file.

        :param config: Configuration dictionary.
        """
        self.config = config
        self.patches_path = self.config.get("DEFAULT", "config.results_path")
        self.json_path = self.config.get("DEFAULT", "config.issues_path")
        self.project_root = self.config.get("DEFAULT", "project_root", fallback=os.getcwd())
        self.data = self._load_json()

    def _load_json(self) -> List[Dict]:
        """
        Load the JSON data from the provided file.

        :return: Parsed JSON data.
        """
        if not os.path.isfile(self.json_path):
            raise FileNotFoundError(f"JSON file not found: {self.json_path}")

        with open(self.json_path, "r") as file:
            return json.load(file)

    def does_patch_file_exist(self, patch_path: str) -> bool:
        """
        Validate if a patch file exists.

        :param patch_path: Path to the patch file.
        :return: True if the patch file exists, False otherwise.
        """
        return os.path.isfile(patch_path)

    def sanitize_patch_content(self, patch_content: str) -> str:
        """
        Ensure that the patch content uses Unix-style line endings and ends with a newline.

        :param patch_content: The raw patch content.
        :return: Sanitized patch content.
        """
        # Convert CRLF to LF
        sanitized_content = patch_content.replace('\r\n', '\n').replace('\r', '\n')

        # Ensure the patch ends with a newline
        if not sanitized_content.endswith('\n'):
            sanitized_content += '\n'

        return sanitized_content

    def normalize_line_endings(self, target_file: str):
        """
        Convert all line endings in the target file to Unix-style LF.

        :param target_file: Path to the target file.
        """
        full_path = os.path.join(self.project_root, target_file)
        if not os.path.isfile(full_path):
            print(f"Target file not found for normalization: {full_path}")
            return
        try:
            with open(full_path, 'rb') as f:
                content = f.read()
            # Convert CRLF to LF
            content = content.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
            with open(full_path, 'wb') as f:
                f.write(content)
            print(f"Line endings normalized to LF for {full_path}")
        except Exception as e:
            print(f"Error normalizing line endings for {full_path}: {e}")

    def normalize_all_line_endings(self):
        """
        Normalize line endings for all Java files in the project directory.
        """
        for root, dirs, files in os.walk(self.project_root):
            for file in files:
                if file.endswith('.java'):
                    full_path = os.path.join(root, file)
                    try:
                        with open(full_path, 'rb') as f:
                            content = f.read()
                        # Convert CRLF to LF
                        content = content.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
                        with open(full_path, 'wb') as f:
                            f.write(content)
                        print(f"Line endings normalized to LF for {full_path}")
                    except Exception as e:
                        print(f"Error normalizing line endings for {full_path}: {e}")

    def apply_patch(self, patch_content: str, target_file: str) -> bool:
        """
        Apply a single patch using the `patch` command by passing patch content directly.

        :param patch_content: The patch data as a string.
        :param target_file: Path to the target file where the patch will be applied.
        :return: True if the patch was successfully applied, False otherwise.
        """
        try:
            # Sanitize the patch content
            patch_content = self.sanitize_patch_content(patch_content)

            # Normalize the target file's line endings
            self.normalize_line_endings(target_file)

            print(f"Applying patch to {target_file} with patch content:\n{patch_content}")

            # Construct the `patch` command with additional options
            command = [
                "patch",
                "-f",                  # Force patch without prompting
                "-N",                  # Ignore patches that have already been applied
                "--fuzz=3",            # Allow fuzz factor of 3
                '--ignore-whitespace',
                '--no-backup-if-mismatch',
                '--reject-file=/dev/null',
                target_file            # Target file to apply the patch
            ]

            # Run the `patch` command, passing the patch content via stdin
            result = subprocess.run(
                command,
                input=patch_content,    # Pass patch content to stdin
                cwd=self.project_root,  # Ensure correct working directory
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Debugging: Print stdout and stderr
            print(f"Patch stdout: {result.stdout}")
            print(f"Patch stderr: {result.stderr}")

            # Check the result of the patch command
            if result.returncode == 0:
                print(f"Patch applied successfully to {target_file}")
                return True
            else:
                print(f"Failed to apply patch to {target_file}\nError: {result.stderr}\nOutput: {result.stdout}")
                # Optionally, read the reject file if it exists
                rej_file = f"{target_file}.rej"
                if os.path.isfile(os.path.join(self.project_root, rej_file)):
                    with open(os.path.join(self.project_root, rej_file), 'r') as rej:
                        reject_content = rej.read()
                        print(f"Rejects saved to {rej_file}:\n{reject_content}")
                return False

        except Exception as e:
            print(f"Exception occurred while applying patch to {target_file}: {e}")
            return False

    def apply_patches(self):
        """
        Iterate over the JSON data and apply all patches using their content directly.
        """
        # Normalize all Java files before applying patches
        self.normalize_all_line_endings()

        for item in self.data:
            for sub_item in item.get("items", []):
                for patch_info in sub_item.get("patches", []):
                    patch_path = os.path.join(self.patches_path, patch_info.get("path"))
                    target_file = sub_item.get("textrange", {}).get("file")

                    if patch_path and target_file:
                        if self.does_patch_file_exist(patch_path):
                            try:
                                with open(patch_path, 'r') as pf:
                                    patch_content = pf.read()
                                success = self.apply_patch(patch_content, target_file)
                                if not success:
                                    print(f"Patch application failed for {patch_path} on {target_file}")
                            except Exception as e:
                                print(f"Error reading patch file {patch_path}: {e}")
                        else:
                            print(f"Patch file not found: {patch_path}")