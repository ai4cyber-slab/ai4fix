import os
import csv
import json
import time

from labels import *
from pydantic import BaseModel, Field
from collections import defaultdict
from diff_filtering import *
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser


REPO = 'struts'
PR_NUM = 252
RUN_TYPE = 'skipping_tests+interfaces'
GPT_MODEL = 'gpt-4-0125-preview'
TEMPERATURE = 0
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

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
    reason: str = Field(
        description="Provide a detailed explanation for your answer. "
                    "If re-running is not worth it, explain why.")

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
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=TEMPERATURE, model_name=GPT_MODEL)


# Initializing log time and statistics
current_time = int(time.time())
category_stats = defaultdict(lambda: {'count': 0})


# Logging basic information into txt logs
with open(f"Logs/multi_shot/{REPO}/{RUN_TYPE}/txt_logs/{GPT_MODEL}_{current_time}.txt", "a") as log_file:
    log_file.write(f"File: {REPO}, pull request #{PR_NUM}\n"
                   f"Model: {GPT_MODEL}\n\n")


# Preparing csv logs   
header = ['Repo', 'PR', 'Model', 'Diff number', 'Category', 'Class label', 'Output', 'Stat', 'Reason']

csv_rows = []
csv_row = []
csv_row.append(REPO)
csv_row.append(PR_NUM)
csv_row.append(GPT_MODEL)

label_categories = []
if REPO == 'storm':
    with open(f'scripts/csv_labels/storm_cats.csv', mode='r') as file:
        reader = csv.reader(file)
        next(reader)
        for row in reader:
            label_categories.append(row)
else:
    with open(f'scripts/csv_labels/struts_cats.csv', mode='r') as file:
        reader = csv.reader(file)
        next(reader)
        for row in reader:
            label_categories.append(row)


# Inference
exact = 0
diff_number = 0
processed_diffs = 0
folder_path = 'original_json_files'
stat = {'tp': 0, 'tn': 0, 'fp': 0, 'fn': 0}

for filename in os.listdir(folder_path):
    
    file_path = os.path.join(folder_path, filename)

    if filename.endswith(f"{REPO}.json"):
        repo_name = REPO
        pr = PR_NUM
        path = f'original_cloned_repos/{REPO}'

        # Process the JSON file
        with open(file_path, 'r') as file:
            data = json.load(file)

    else:
        continue

    for pull in data['pulls']:
        if pull['number'] == pr:
            for commit in pull['commits']:

                for file in commit['files']:
                    diff_number += 1
                    diff = file['diff_file']
                    
                    unnecessary_diff = remove_unnecessary_diff(path, diff)
                    if unnecessary_diff:
                        print(str(diff_number) + ' removed')
                        continue

                    csv_row.append(diff_number)
                    csv_row.append(label_categories[diff_number - 1][1]) # Category of the diff
                    csv_row.append(label_categories[diff_number - 1][0]) # Class label of the diff

                    try:
                        diff_prompt = describe_prompt.format(diff=diff)
                        diff_response = llm.invoke(diff_prompt)
                        description = diff_response.content

                        re_run_prompt = classify_prompt.format(diff=diff, description=description)
                        re_run_response = llm.invoke(re_run_prompt)
                        
                        parsed_re_running = label_parser.parse(re_run_response.content)
                        output = parsed_re_running.worth_to_re_run.lower().strip()
                        reason = parsed_re_running.reason

                        if output == 'yes':
                            label = 'security'
                        else:
                            label = 'not'

                        csv_row.append(label)
                   
                        # Update counts and total ratings for each category
                        category_stats[label]['count'] += 1

                        # Log input and output
                        with open(f"Logs/multi_shot/{REPO}/{RUN_TYPE}/txt_logs/{GPT_MODEL}_{current_time}.txt", "a") as log_file:
                            log_file.write(f"Diff number: {diff_number}\nInput 1:\n{diff_prompt}\nOutput 1: {diff_response.content}\n\n"
                                           f"Input 2:\n{re_run_prompt}\nOutput 2: {re_run_response.content}\n\n")
                        
                        if repo_name == 'storm':
                            labels = storm_labels()
                        else:
                            labels = struts_labels()
                        
                        if labels[diff_number] == 'security':
                            if label == 'security':
                                exact += 1
                                stat['tp'] += 1
                                csv_row.append('TP')
                            else:
                                stat['fn'] += 1
                                csv_row.append('FN')

                        if labels[diff_number] == 'not':
                            if label == 'not':
                                exact += 1
                                stat['tn'] += 1
                                csv_row.append('TN')
                            else:
                                stat['fp'] += 1
                                csv_row.append('FP')

                        csv_row.append(reason)
                        csv_rows.append(csv_row)
                        csv_row = csv_row[:3]

                        print(diff_number)
                        processed_diffs += 1

                    except Exception as e:
                        print("couldn't process - ", e)
                        csv_row = csv_row[:3]
                        continue


# Calculate mean confidence for each category
storm_stat = {'security': 22, 'not': 23}
struts_stat = {'security': 15, 'not': 46}

error_num = 0
result_stat = []
for catetgory, stats in category_stats.items():
    count = stats['count']
    
    result_stat.append({
        catetgory: count
    })

    if REPO == 'storm':
        error_num += abs(storm_stat[catetgory] - count)
    else:
        error_num += abs(struts_stat[catetgory] - count)


# Logging into csv
with open(f"Logs/multi_shot/{REPO}/{RUN_TYPE}/csv_logs/{GPT_MODEL}_{current_time}.csv", "w", newline='') as file:
    writer = csv.writer(file)
    writer.writerow(header)

    for row in csv_rows:
        writer.writerow(row)


# Statistics
accuracy = exact/processed_diffs
precision = stat['tp']/(stat['tp'] + stat['fp'])
recall = stat['tp']/(stat['tp'] + stat['fn'])
f1_score = 2*precision*recall/(precision + recall)


# Logging statistics
with open(f"Logs/multi_shot/{REPO}/{RUN_TYPE}/txt_logs/{GPT_MODEL}_{current_time}.txt", "a") as log_file:
    log_file.write(f"Number of diff files: {diff_number}\n"
                   f"Number of processed files: {processed_diffs}\n"
                   f"Statistics: {result_stat}\n"
                   f"Error number: {error_num}\n"
                   f"Accuracy: {accuracy}\n"
                   f"Precision: {precision}\n"
                   f"Recall: {recall}\n"
                   f"F1 Score: {f1_score}")
