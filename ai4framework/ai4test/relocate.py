import glob
import os
import shutil
from pathlib import Path
from ai4test.database import get_java_file_paths
import re
from datetime import datetime

class SmartTestRelocator:
    def __init__(self, *skip_dirs):
        """
        :param skip_dirs: Multiple paths where .java.txt files may exist to indicate skipping
        """
        self.skip_dirs = [Path(d) for d in skip_dirs]

    def get_package_from_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('package '):
                        return line.replace('package ', '').replace(';', '').strip()
        except Exception as e:
            print(f"[ERROR] Failed reading {file_path}: {e}")
        return ""

    def clean_test_name_for_matching(self, test_name):
        name = test_name.replace('Test', '')
        name = ''.join([c for c in name if not c.isdigit() and c != '_'])
        return name

    
    def find_matching_source(self, sample_base_name, expected_package_path):
        """Find a matching source file based on class name AND package path"""
        candidates = []
        sources_files = [Path(f) for f in get_java_file_paths(sample_base_name)]
        for src_file in sources_files:
            if src_file.stem == sample_base_name:
                # Check if package path matches inside full path
                if expected_package_path in str(src_file.parent):
                    candidates.append(src_file)
        return candidates


    def find_matching_source(self, sample_base_name, expected_package_path):
        candidates = []
        sources_files = [Path(f) for f in get_java_file_paths(sample_base_name)]
        for src_file in sources_files:
            if src_file.stem == sample_base_name:
                if expected_package_path:
                    # If package path is known, check if it matches
                    if expected_package_path in str(src_file.parent):
                        candidates.append(src_file)
                else:
                    # No package case: only accept files very close to src/main/java
                    if 'src/main/java' in str(src_file) or 'src\\main\\java' in str(src_file):
                        candidates.append(src_file)
        return candidates

    def should_skip_test(self, test_name):
        """Check if .java.txt file exists in any of the skip folders"""
        for skip_dir in self.skip_dirs:
            skip_file_runtime = skip_dir / f"TestOutput-{test_name}.java.txt"
            skip_file_compiler = skip_dir / f"CompilerOutput-{test_name}.java.txt"
            if skip_file_runtime.exists() or skip_file_compiler.exists():
                return True
        return False


    def relocate_tests(self, generated_tests_dir):
        test_files = glob.glob(os.path.join(generated_tests_dir, "**/*.java"), recursive=True)
        
        for test_file in test_files:
            test_file_path = Path(test_file)
            test_class_name = test_file_path.stem

            if self.should_skip_test(test_class_name):
                print(f"[SKIP] {test_class_name} marked to skip.")
                continue

            package = self.get_package_from_file(test_file_path)
            package_path = package.replace('.', '/') if package else ''

            sample_base_name = self.clean_test_name_for_matching(test_class_name)

            matches = self.find_matching_source(sample_base_name, package_path)

            if not matches:
                print(f"[WARN] No match found for {test_class_name}, skipping...")
                continue

            matched_source = matches[0]

            try:
                idx = matched_source.parts.index('src')
            except ValueError:
                print(f"[WARN] 'src' not found in {matched_source}, skipping...")
                continue

            new_parts = list(matched_source.parts[:idx+1]) + ['test', 'java'] + list(matched_source.parts[idx+3:-1])
            dest_dir = Path(*new_parts)

            dest_dir.mkdir(parents=True, exist_ok=True)

            # Final destination file (before checking conflict)
            dest_file = dest_dir / test_file_path.name

            if dest_file.exists():
                # Handle conflict: create a unique filename
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                new_name = f"{str(test_class_name).replace('Test', f'_{timestamp}Test')}{test_file_path.suffix}"
                new_dest_file = dest_dir / new_name

                shutil.copy(test_file_path, new_dest_file)
                self.update_class_name(new_dest_file, test_class_name, new_name.replace('.java', ''))

                print(f"[CONFLICT-RESOLVED] {test_file} → {new_dest_file} (class name updated)")
            else:
                shutil.copy(test_file_path, dest_file)
                print(f"[OK] Moved {test_file} → {dest_file}")

    def update_class_name(self, file_path, old_class_name, new_class_name):
        """Safely update the class name inside the Java file using regex."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Regex pattern to match class declaration
        pattern = r"\b(public\s+)?(abstract\s+|final\s+)?class\s+" + re.escape(old_class_name) + r"\b"
        replacement = r"\1\2class " + new_class_name
        new_content = re.sub(pattern, replacement, content, count=1)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)




if __name__ == "__main__":
    pass
    # source_files = [
    #     "/app/pelo-project/src/main/java/example/b/B.java",
    #     "/app/pelo-project/src/main/java/example/Main.java",
    #     "/app/pelo-project/src/main/java/example/ArrayDemo.java",
    #     "/app/pelo-project/src/main/java/example/a/MutableInit.java",
    #     "/app/pelo-project/src/main/java/example/NullPath.java",
    #     "/app/pelo-project/src/main/java/example/MyDate.java",
    #     "/app/pelo-project/src/main/java/example/a/Mutable.java"
    # ]

    # skip_folder_runtime_error = os.path.join(target_dir, "test_output")
    # skip_folder_compile_error = os.path.join(target_dir, "compiler_output")

    # relocator = SmartTestRelocator(
    #     skip_folder_runtime_error,
    #     skip_folder_compile_error
    # )

    # relocator.relocate_tests('/path/to/generated/tests/')
