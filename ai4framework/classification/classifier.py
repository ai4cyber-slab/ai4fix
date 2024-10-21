"""
AI4Framework Classifier Module

This module provides functionality for classifying code changes in a Git repository
based on their potential security impact. It uses OpenAI's GPT models to analyze
diff files and determine if security testing should be re-run.

Usage:
    python classifier.py -r <repo_path> -c <commit_sha> -k <openai_api_key> [-m <model>] [-t <temperature>]

Arguments:
    -r, --repo_path: Path to the Git repository (required)
    -c, --commit_sha: Commit hash to analyze (required)
    -m, --model: GPT model to use (default: "gpt-4o")
    -t, --temperature: Temperature setting for the GPT model (default: 0)
    -k, --key: OpenAI API key (required)

The script outputs results to both a text log file and a JSON file in the 'out' directory.
"""

import os
import re
import sys
import git
import json
import argparse
import subprocess
from pydantic import BaseModel, Field
from diff_filtering import remove_unnecessary_diff
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from management.repo_manager import RepoManager

# Creating the parser
parser = argparse.ArgumentParser(description="Classifier script with arguments",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

# Adding the arguments
parser.add_argument("-r", "--repo_path", type=str, help="The path of your repository", required=True)
parser.add_argument("-c", "--commit_sha", type=str, help="The hash of the commit", required=True)
parser.add_argument("-m", "--model", type=str, help="The name of the GPT-model", default="gpt-4o")
parser.add_argument("-t", "--temperature", type=str, help="The temperature of the model", default=0)
parser.add_argument("-k", "--key", type=str, help="Your OpenAI API key", required=True)

# Parsing the arguments
args = parser.parse_args()

output_data = {
    "repository_path": args.repo_path,
    "commit_sha": args.commit_sha,
    "gpt_model": args.model,
    "temperature": args.temperature,
    "security_relevant_files": []
}

# Logging basic information into a txt file
starting_dir = os.path.dirname(os.path.abspath(__file__)) # The directory where the script is located
out_dir = os.path.join(starting_dir, 'out')
os.makedirs(out_dir, exist_ok=True)
txt_path = os.path.join(out_dir, args.commit_sha)
with open(f"{txt_path}.txt", "a") as log_file:
    log_file.write(f"Repository path: {args.repo_path}\n"
                    f"Commmit hash: {args.commit_sha}\n"
                    f"Model: {args.model}\n"
                    f"Temperature: {args.temperature}\n\n")


def error_and_log_handling(message, consol):
    """
    Handle errors and logging.

    Args:
        message (str): The message to log.
        consol (bool): If True, also print the message to console.
    """
    with open(f"{txt_path}.txt", "a") as log_file:
        log_file.write(message + "\n")
    if consol:
        print(message)


def diff_line_positions(diff_content):
    """
    Retrieve the start and end positions of changes in a diff file.

    Args:
        diff_content (str): The content of the diff file.

    Returns:
        list: A list of dictionaries containing start and end positions of changes.
    """
    line_positions = []

    diff_lines = diff_content.split('\n')
    for line in diff_lines:
        if '@@' in line:
            start_position = int(line.split(' ')[2].split(',')[0][1:])
            changed_lines = int(line.split(' ')[2].split(',')[1])
            end_position = start_position + changed_lines - 1
            line_positions.append({"start_position": start_position, "end_position": end_position})

    return line_positions


def list_changed_files(repo_path, commit_hash):
    """
    List the files changed in a specific commit.

    Args:
        repo_path (str): Path to the Git repository.
        commit_hash (str): Hash of the commit to analyze.

    Returns:
        list: A list of changed file paths, or None if an error occurs.
    """
    try:
        repo_manager = RepoManager(repo_path, commit_hash)
        
        changed_files = repo_manager.get_changed_files()
        
        if changed_files:
            error_and_log_handling(f"Changed files in commit {commit_hash}: {changed_files}", True)
        else:
            error_and_log_handling(f"No files changed in commit {commit_hash}.", True)
        
        return changed_files
    
    except git.exc.InvalidGitRepositoryError:
        error_and_log_handling(f"The directory {repo_path} is not a valid Git repository.", True)
        sys.exit(1)

    except git.exc.GitCommandError:
        error_and_log_handling(f"Commit {commit_hash} not found.", True)
        sys.exit(1)

    except git.exc.BadName:
        error_and_log_handling(f"Commit {commit_hash} not found or invalid.", True)
        sys.exit(1)

    except Exception as e:
        error_and_log_handling(f"An error occurred while retrieving the commit files:\n{e}", True)
        sys.exit(1)


def main():
    """
    Main function to run the classifier.

    This function initializes the GPT model, retrieves changed files,
    analyzes each file's diff, and determines if security testing should be re-run.
    Results are logged and saved to a JSON file.
    """
    DESCRIPTION_PROMPT = """
    You are a code analyst and you explain how codes work to expert programmers.
    Examine the given commit diff file and give such a programmer a detailed description of it's operation.

    The output should be formatted as a single string.

    Diff file:
    ```
    {diff}
    ```
    """

    CLASSIFYING_PROMPT = """
    You are a security evaluator, tasked with analysing code changes to identify their impact on system security.
    The provided diff file below was previously run for such security testing, which did not find any issue with the code.
    Based on the changes in this diff file, concentrating solely on the lines that start with '+' or '-' and it's description, is it worth re-running the security testing on the modified file?

    {output_instructions}

    The diff file:
    ```
    {diff}

    ```

    The diff file's description:
    ```
    {description}
    ```

    Important that testing is a costly operation.
    Determine the answer considering the immediate implications of the changes on system security, especially for modifications to critical components.
    """


    # Initializing prompt templates
    class LabelOutput(BaseModel):
        worth_to_re_run: str = Field(
            description="A string whose value is one of the following: "
                        "['yes' (if re-running the security tests on the given diff file is necessary), "
                        "'no' (if re-running the security tests on the given diff file is not worth it)].")

    describe_prompt = PromptTemplate(
        template=DESCRIPTION_PROMPT,
        input_variables=["diff"]
    )

    label_parser = PydanticOutputParser(pydantic_object=LabelOutput)
    label_instructions = label_parser.get_format_instructions()
    classify_prompt = PromptTemplate(
        template=CLASSIFYING_PROMPT,
        input_variables=["diff", "description"],
        partial_variables={"output_instructions": label_instructions}
    )


    # Initializing the LLM
    try:
        llm = ChatOpenAI(api_key=args.key, temperature=args.temperature, model=args.model)
        llm.invoke("Testing the LLM.")
    except Exception as e:
        error_and_log_handling(f"An error occurred while initializing the llm: {e}", True)
        sys.exit(1)


    # Inference
    try:
        changed_files = list_changed_files(args.repo_path, args.commit_sha)
        if changed_files is not None:
            error_and_log_handling("Successfully retrieved the commit files.", False)

        repo_manager = RepoManager(args.repo_path, args.commit_sha)
        parent = repo_manager.get_parent_commit()
        if parent:
            error_and_log_handling(f"Successfully retrieved the parent commit: {parent}.", False)
            filter_path = os.path.join(args.repo_path, 'filter.txt')
            if os.path.exists(filter_path):
                os.remove(filter_path)

            for file in changed_files:
                if file.endswith('.java'):
                    git_diff_file = os.path.join('changes.diff')
                    os.system(f'git diff {parent} {args.commit_sha} -- {file} > {git_diff_file}') # Creating the diff file
                    error_and_log_handling(f"Successfully created the diff file of {file}.", False)

                    with open(git_diff_file, 'r', encoding='latin-1') as f:
                        diff_content = f.read()

                    unnecessary_diff = remove_unnecessary_diff(args.repo_path, diff_content)
                    if unnecessary_diff:
                        error_and_log_handling(f"The diff of {file} is unnecessary, it has been removed.\n", True)
                        continue

                    try:
                        diff_prompt = describe_prompt.format(diff=diff_content)
                        diff_response = llm.invoke(diff_prompt)
                        description = diff_response.content

                        re_run_prompt = classify_prompt.format(diff=diff_content, description=description)
                        re_run_response = llm.invoke(re_run_prompt)
                        
                        parsed_re_running = label_parser.parse(re_run_response.content)
                        output = parsed_re_running.worth_to_re_run.strip().lower()

                        if output == 'yes':
                            line_positions = diff_line_positions(diff_content)
                            output_dict = {
                                "file_path": file,
                                "security_relevant_lines": line_positions
                            }
                            output_data['security_relevant_files'].append(output_dict)
                            # for symbolic execution
                            match = re.match(f'^(.*){os.sep}src', file)
                            if match:
                                before_src = match.group(1)
                                filter_path = os.path.join(before_src, 'filter.txt')
                            with open(filter_path, 'a') as filter_file:
                                if filter_file.tell() == 0:
                                    filter_file.write("-.*\n")
                                filter_file.write(f"+.*{file}\n")
                            error_and_log_handling(f"{file} was labeled as security relevant.\n", True)
                        else:
                            error_and_log_handling(f"{file} was labeled as not security relevant.\n", True)
                            
                        # os.system('rm changes.diff')
                        os.remove(git_diff_file)

                    except Exception as e:
                        error_and_log_handling(f"An error occurred during the labeling of {file}:\n{e}", True)
                        # os.system('rm changes.diff')
                        os.remove(git_diff_file)
                        continue    
        
        else:
            error_and_log_handling(f'No changed files in commit {args.commit_sha}', True)
            sys.exit(1)

    except Exception as e:
        error_and_log_handling(f"An error occurred during the inference:\n{e}", True)
        sys.exit(1)

    os.chdir(starting_dir)


    # Logging the output
    json_path = os.path.join(out_dir, args.commit_sha)
    with open(f"{json_path}.json", "a") as log_file:
        json.dump(output_data, log_file, indent=4)
    

if __name__ == "__main__":
    main()
