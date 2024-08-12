# from utils.logger import logger
import subprocess
import json

# todo: a certain file 'model_test_with_snippet.py' is mentioned in the flowchart but couldn't find it ai4fw repo.


class FixGenerator:
    def __init__(self, config):
        self.config = config

    def generate_fixes(self, issues_file):
        # logger.info("Fix generation started")
        # todo: use the fakeAiFixCode.ts file to get the issues from sym execution and sast engine and generate the fixes
        # todo: receive the issues from the SAST engine too. (issues.json)
        # return patches
        pass

    def getIssuesSync(self, file_path):
        try:
            result = subprocess.run(
                ['ts-node' 'C:/Users/HP/slab/ai4fix/vscode-plugin/src/services/fakeAiFixCode.ts', file_path],
                capture_output=True,
                text=True,
                check=True
            )
            try:
                issues = json.loads(result.stdout)
                return issues
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON output: {e}")
                return None
        except subprocess.CalledProcessError as e:
            print(f"Error during execution: {e.stderr}")
            return None
        
    def call_ts_function(self, func_name, *args):
        try:
            command = [
                'node', 
                'C:/Users/HP/slab/ai4fix/vscode-plugin/out/services/fakeAiFixCode.js', 
                func_name,
                *args
            ]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
            try:
                return result.stdout
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON output: {e}")
                return None
        except subprocess.CalledProcessError as e:
            print(f"Error during execution: {e.stderr}")
            return None
        
if __name__ == '__main__':
    fix_generator = FixGenerator(None)
    # print(fix_generator.getIssuesSync('C:/Users/HP/slab/ai4fix/test-project/jsons.lists'))
    result = fix_generator.call_ts_function('printName', 'Youou')
    print(result)