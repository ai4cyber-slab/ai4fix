import os
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
# from ...ai4framework.utils.logger import logger


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
script_dir = os.path.dirname(os.path.abspath(__file__)) # The directory where the script is located
txt_path = os.path.join(script_dir, args.commit_sha)
with open(f"{txt_path}.txt", "a") as log_file:
    log_file.write(f"Repository path: {args.repo_path}\n"
                    f"Commmit hash: {args.commit_sha}\n"
                    f"Model: {args.model}\n"
                    f"Temperature: {args.temperature}\n\n")


# Method for handling errors and logs
def error_and_log_handling(message, consol):
    with open(f"{txt_path}.txt", "a") as log_file:
        log_file.write(message + "\n")
    if consol:
        print(message)


# Method for retrieving the start and end position of changes in a diff file
def diff_line_positions(diff_content):
    line_positions = []

    diff_lines = diff_content.split('\n')
    for line in diff_lines:
        if '@@' in line:
            start_position = int(line.split(' ')[2].split(',')[0][1:])
            changed_lines = int(line.split(' ')[2].split(',')[1])
            end_position = start_position + changed_lines - 1
            line_positions.append({"start_position": start_position, "end_position": end_position})

    return line_positions


# Method for listing out changed files in a commit
def list_changed_files(repo_path, commit_hash):
    try:
        # Check if the directory exists
        if not os.path.isdir(repo_path):
            print(f"The directory {repo_path} does not exist.")

            # Exiting the script with an error code
            sys.exit(1)

        # Opening the repository
        repo = git.Repo(repo_path)
        
        # Getting the commit object
        commit = repo.commit(commit_hash)
        
        # Getting the list of changed files
        changed_files = commit.stats.files.keys()
        
        return list(changed_files)
    
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


    # Initializing prompt templates
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

            os.chdir(args.repo_path) # Changing the location to the repo folder 
            git_command = f'git log --pretty=%P -n 1 {args.commit_sha}' # Retrieving the parent commit
            result = subprocess.run(git_command, shell=True, stdout=subprocess.PIPE, text=True)
            parent = result.stdout.strip().split()[0]
            error_and_log_handling("Successfully retrieved the parent commit.\n", False)

            for file in changed_files:
                if file.endswith('.java'):
                    os.system(f'git diff {parent} {args.commit_sha} -- {file} > changes.diff') # Creating the diff file
                    error_and_log_handling(f"Successfully created the diff file of {file}.", False)

                    with open('changes.diff', 'r', encoding='latin-1') as f:
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
                            error_and_log_handling(f"{file} was labeled as security relevant.\n", True)
                        else:
                            error_and_log_handling(f"{file} was labeled as not security relevant.\n", True)
                            
                        os.system('rm changes.diff')

                    except Exception as e:
                        error_and_log_handling(f"An error occurred during the labeling of {file}:\n{e}", True)
                        os.system('rm changes.diff')
                        continue    
        
        else:
            error_and_log_handling(f'No changed files in commit {args.commit_sha}', True)
            sys.exit(1)

    except Exception as e:
        error_and_log_handling(f"An error occurred during the inference:\n{e}", True)
        sys.exit(1)

    os.chdir(script_dir)


    # Logging the output
    json_path = os.path.join(script_dir, args.commit_sha)
    with open(f"{json_path}.json", "a") as log_file:
        json.dump(output_data, log_file, indent=4)
    

if __name__ == "__main__":
    main()
