import json
import os
import subprocess
from typing import Dict, List, Tuple
from configparser import ConfigParser
from utils.logger import logger
import time

class PatchApplier:
    """
    A class to read patches from a JSON configuration and apply them.
    """

    def __init__(self, config: ConfigParser):
        self.config = config
        self.patches_path = self.config.get("DEFAULT", "config.results_path")
        self.json_path = self.config.get("DEFAULT", "config.issues_path")
        self.project_root = self.config.get("DEFAULT", "project_root", fallback=os.getcwd())
        self.applied_patches = {}
        self.data = self._load_json()

    def _load_json(self) -> List[Dict]:
        """
        Load the JSON data from the provided file.
        """
        if not os.path.isfile(self.json_path):
            raise FileNotFoundError(f"JSON file not found: {self.json_path}")

        with open(self.json_path, "r") as file:
            return json.load(file)

    def does_patch_file_exist(self, patch_path: str) -> bool:
        """
        Validate if a patch file exists.
        """
        return os.path.isfile(patch_path)

    def parse_patch_ranges(self, patch_content: str) -> List[Tuple[int, int]]:
        """
        Parse the patch content to extract line ranges it modifies.

        :param patch_content: The content of the patch file.
        :return: A list of tuples representing start and end line ranges.
        """
        modified_ranges = []
        for line in patch_content.splitlines():
            if line.startswith('@@'):
                parts = line.split(' ')[1]
                start, length = parts[1:].split(',')
                modified_ranges.append((int(start), int(start) + int(length) - 1))
        return modified_ranges

    def is_overlap(self, target_file: str, patch_ranges: List[Tuple[int, int]]) -> bool:
        """
        Check if the patch modifies a range that has already been modified.

        :param target_file: Path to the target file.
        :param patch_ranges: The line ranges the patch modifies.
        :return: True if there is an overlap, False otherwise.
        """
        if target_file not in self.applied_patches:
            self.applied_patches[target_file] = []

        for patch_range in patch_ranges:
            for applied_range in self.applied_patches[target_file]:
                if not (patch_range[1] < applied_range[0] or patch_range[0] > applied_range[1]):
                    return True
        return False

    def mark_applied_ranges(self, target_file: str, patch_ranges: List[Tuple[int, int]]):
        """
        Mark the line ranges of a successfully applied patch.

        :param target_file: Path to the target file.
        :param patch_ranges: The line ranges the patch modifies.
        """
        if target_file not in self.applied_patches:
            self.applied_patches[target_file] = []
        self.applied_patches[target_file].extend(patch_ranges)

    def apply_patch(self, patch_content: str, target_file: str, patch_path: str) -> bool:
        """
        Apply a single patch to the target file.

        :param patch_content: The patch content.
        :param target_file: Path to the target file.
        :param patch_path: Path to the patch file.
        :return: True if the patch was successfully applied, False otherwise.
        """
        try:
            patch_ranges = self.parse_patch_ranges(patch_content)

            if self.is_overlap(target_file, patch_ranges):
                logger.warning(f"Patch overlaps with existing changes in {target_file}. Skipping.")
                return False

            temp_patch_path = os.path.join(self.patches_path, "temp.patch")
            with open(temp_patch_path, "w") as temp_patch_file:
                temp_patch_file.write(patch_content)

            command = ["patch", "--dry-run", "-p0", "-i", temp_patch_path]
            result = subprocess.run(
                command,
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if result.returncode != 0:
                logger.error(f"Patch validation failed for {target_file}: {result.stderr}")
                os.remove(temp_patch_path)
                return False

            command = ["patch", "--no-backup-if-mismatch", "--reject-file=/dev/null", "-p0", "-i", patch_path]
            result = subprocess.run(
                command, cwd=self.project_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            if result.returncode == 0:
                # Mark ranges as applied
                self.mark_applied_ranges(target_file, patch_ranges)
                logger.info(f"Successfully applied patch to {target_file}")
                os.remove(temp_patch_path)
                return True
            else:
                logger.error(f"Failed to apply patch to {target_file}: {result.stderr}")
                os.remove(temp_patch_path)
                return False

        except Exception as e:
            logger.error(f"Exception occurred while applying patch to {target_file}: {e}")
            return False

    def apply_patches(self):
        """
        Iterate over the JSON data and apply all patches.
        """
        start_time = time.time()

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
                                self.apply_patch(patch_content, target_file, patch_path)
                            except Exception as e:
                                logger.error(f"Exception occurred while applying patch to {target_file}: {e}")
                        else:
                            logger.warning(f"Patch file not found: {patch_path}")

        logger.info("Automatic patch application finished.")
        logger.info(f"Total time taken: {time.time() - start_time} seconds.")