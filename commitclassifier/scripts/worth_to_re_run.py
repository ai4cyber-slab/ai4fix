import os
import json
import time
from labels import *
from pydantic import BaseModel, Field
from collections import defaultdict
from diff_filtering import *
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser


PR_NUM = '#448'
RUN_TYPE = 'worth_to_re_run'
REPO = 'storm'
TEMPERATURE = 0
GPT_MODEL = 'gpt-3.5-turbo-0125'
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')


PROMPT = """You are a security evaluator, tasked with analyzing code changes to identify their impact on system security.
Your focus is on detecting modifications that directly affect critical security components such as authentication mechanisms, encryption algorithms, access control procedures, and logging levels related to security events.
The provided diff file below was previously run for such security testing.
Based on the changes in this diff file, concentrating solely on the lines that start with '+' or '-', is it worth re-running the security testing on this same file?
{format_instructions}
You will also receive context containing class(es) where the methods in the diff file were called. If no methods are present in the diff file, this context will be empty.
Use this extra information for your evaluation.
Diff file:
```
{diff_file}
```
Context:
```
{context}
```
Important that testing is a costly operation.
Determine the answer considering the immediate implications of the changes on system security, especially for modifications to critical components."""


class Output(BaseModel):
    worth_to_re_run: str = Field(
        description="A string whose value is one of the following: "
                    "['yes' (if re-running the security tests on the given diff file is necessary), "
                    "'no' (if re-running the security tests on the given diff file is not worth it)].")
    reason: str = Field(
        description="Provide a detailed explanation for your answer. "
                    "If re-running is not worth it, explain why.")
    confidence: int = Field(
        description="Rate your confidence in your assessment from 0-10, "
                    "with 0 being not confident and 10 being extremely confident.")


# Initializing the LLM
llm = ChatOpenAI(model_name=GPT_MODEL, temperature=TEMPERATURE, openai_api_key=OPENAI_API_KEY)

parser = PydanticOutputParser(pydantic_object=Output)
format_instructions = parser.get_format_instructions()
prompt_template = PromptTemplate(
    template=PROMPT,
    input_variables=["diff_file", "context"],
    partial_variables={"format_instructions": format_instructions},
)


# Initializing log file
current_time = int(time.time())
category_stats = defaultdict(lambda: {'count': 0, 'total_confidence': 0})

with open(f"Logs/{RUN_TYPE}/{REPO}/txt_logs/{GPT_MODEL}_{current_time}.txt", "a") as log_file:
    log_file.write(f"File: {REPO}, pull request {PR_NUM}\n"
                   f"Model: {GPT_MODEL}\n\n")


# Inference
exact = 0
number_of_diffs = 0
processed_diffs = 0
folder_path = 'original_json_files'
stat = {'tp': 0, 'tn': 0, 'fp': 0, 'fn': 0}

for filename in os.listdir(folder_path):
    index = 0
    file_path = os.path.join(folder_path, filename)

    if filename.endswith(f"{REPO}.json"):
        repo_name = REPO
        pr = int(PR_NUM.replace('#', ''))
        path = f"original_cloned_repos/{repo_name}"

        # Process the JSON file
        with open(file_path, 'r') as file:
            data = json.load(file)

    # elif filename.endswith(f"{REPO.split('+')[1]}.json"):
        # repo_name = REPO.split('+')[1]
        # pr = int(PR_NUM.split(' ')[1].replace('#', ''))
        # path = f'original_cloned_repos/{repo_name}'

        # Process the JSON file
        # with open(file_path, 'r') as file:
            # data = json.load(file)
    else:
        continue

    for pull in data['pulls']:
        if pull['number'] == pr:

            # print(repo_name)
            # with open(f"Logs/{RUN_TYPE}/{REPO}/txt_logs/{GPT_MODEL}_{current_time}.txt", "a") as log_file:
                # log_file.write(f"Repo: {repo_name}\n\n")

            for commit in pull['commits']:

                for file in commit['files']:
                    index += 1
                    number_of_diffs += 1
                    diff = file['diff_file']

                    cleaned_diff = remove_unnecessary_diff(path, diff)
                    if cleaned_diff:
                        print(str(index) + ' removed')
                        continue

                    diff_method_names = diff_methods(diff)
                    context = find_method_calls(path, diff_method_names)        
                    try:
                        prompt = prompt_template.format(diff_file=diff, context=context)
                        response = llm.invoke(prompt)

                        # Extract relevant attributes
                        parsed_output = parser.parse(response.content)
                        output = parsed_output.worth_to_re_run
                        if output.lower() == 'yes':
                            label = 'security'
                        else:
                            label = 'not'
                         
                        # Update counts and total ratings for each category
                        category_stats[label]['count'] += 1
                        category_stats[label]['total_confidence'] += parsed_output.confidence

                        # Log input and output
                        with open(f"Logs/{RUN_TYPE}/{REPO}/txt_logs/{GPT_MODEL}_{current_time}.txt", "a") as log_file:
                            log_file.write(f"Diff number: {index}\nInput: {prompt}\n\nOutput: {response.content + ' -> security_relevancy: ' + label}\n\n")

                        # if repo_name == REPO:
                            labels = storm_labels()
                        # else:
                            # labels = struts_labels()

                        if labels[index] == 'security':
                            if label == 'security':
                                exact += 1
                                stat['tp'] += 1
                            else:
                                stat['fn'] += 1

                        if labels[index] == 'potentially':
                            exact += 1
                            # if label == 'potentially' and sec_rel.split('_')[1] == 'security':
                            if label == "security":
                                stat['tp'] += 1
                            else:
                                stat['tn'] += 1

                        if labels[index] == 'not':
                            if label == 'not':
                                exact += 1
                                stat['tn'] += 1
                            else:
                                stat['fp'] += 1

                        print(index)
                        processed_diffs += 1

                    except Exception as e:
                        print("couldn't process - ", e)
                        continue


# Calculate mean confidence for each category
storm_stat = {'security': 22, 'potentially': 0, 'not': 23}
struts_stat = {'security': 0, 'potentially': 15, 'not': 46}
sum_stat = {'security': storm_stat['security'] + struts_stat['security'], 
           'potentially': storm_stat['potentially'] + struts_stat['potentially'], 
           'not': storm_stat['not'] + struts_stat['not']}


error_num = 0
result_stat = []
for catetgory, stats in category_stats.items():
    count = stats['count']
    total_confidence = stats['total_confidence']
    mean_confidence = total_confidence // count if count > 0 else 0
            
    result_stat.append({
        catetgory: count,
        'mean_conf': mean_confidence
    })

    error_num += abs(storm_stat[catetgory] - count)


# Statistics
accuracy = exact/processed_diffs
precision = stat['tp']/(stat['tp'] + stat['fp'])
recall = stat['tp']/(stat['tp'] + stat['fn'])
f1_score = 2*precision*recall/(precision + recall)


# Logging statistics
with open(f"Logs/{RUN_TYPE}/{REPO}/txt_logs/{GPT_MODEL}_{current_time}.txt", "a") as log_file:
    log_file.write(f"Number of diff files: {number_of_diffs}\n"
                   f"Number of processed files: {processed_diffs}\n"
                   f"Statistics: {result_stat}\n"
                   f"Error number: {error_num}\n"
                   f"Accuracy: {accuracy}\n"
                   f"Precision: {precision}\n"
                   f"Recall: {recall}\n"
                   f"F1 Score: {f1_score}")
