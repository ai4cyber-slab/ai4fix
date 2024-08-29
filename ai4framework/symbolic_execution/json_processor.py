import json
from utils.logger import logger

class JSONProcessor:
    @staticmethod
    def extract_and_clean_json(input_file, output_file):
        def extract_issues(json_file):
            with open(json_file, 'r') as infile:
                data = json.load(infile)

            merged_issues = {}

            for issue in data:
                explanation = issue['explanation']

                for item in issue['items']:
                    if 'trace' in item:
                        del item['trace']

                if explanation not in merged_issues:
                    merged_issues[explanation] = {
                        "id": issue["id"],
                        "name": issue["name"],
                        "explanation": explanation,
                        "tags": issue["tags"],
                        "items": issue["items"]
                    }
                else:
                    merged_issues[explanation]["items"].extend(issue["items"])

            merged_issues_list = list(merged_issues.values())
            return merged_issues_list
        
        issues = extract_issues(input_file)
        
        with open(output_file, 'w') as file:
            json.dump(issues, file, indent=4)
        
        logger.info(f"Extracted and cleaned JSON saved to {output_file}")
