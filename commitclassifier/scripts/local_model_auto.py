import os
import csv
import json
import time
import requests

from labels import *
from collections import defaultdict
from diff_filtering import *
from huggingface_hub import InferenceClient
from langchain.prompts import PromptTemplate


REPO = 'storm'
MODEL = 'qwen/CodeQwen1.5-7B-Chat'
PR_NUM = 448
RUN_TYPE = 'skipping_tests+interfaces'

# API_KEY = os.getenv('DeepSeek_API_KEY')
API_TOKEN = os.getenv('API_TOKEN')
HEADER = {"Authorization": f"Bearer {API_TOKEN}"}
API_URL = f"https://api-inference.huggingface.co/models/{MODEL}"

CLIENT = InferenceClient(MODEL, token=API_TOKEN)

SPACE_URL = "https://gcy2v8knprd9c16i.us-east-1.aws.endpoints.huggingface.cloud"
SPACE_HEADER = {
    "Accept" : "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_TOKEN}"
}


def pipeline(prompt):
    output = ''
    for message in CLIENT.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        stream=True,
    ):
        # print(message.choices[0].delta.content, end="")
        try:
            output += message.choices[0].delta.content
        except:
            print('some part of the message was not generated')
            continue
    return output


def query(payload):
    response = requests.post(SPACE_URL, headers=SPACE_HEADER, json=payload)
    try:
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {response.content}")
    except requests.exceptions.RequestException as req_err:
        print(f"Error occurred during request: {req_err}")
    except ValueError as json_err:
        print(f"JSON decode error: {json_err}")
        print(f"Response content: {response.content}")
    return None


def generate_text(input_text):
    try:
        output = query({
            "inputs": input_text,
            "parameters": {
                'return_full_text': False, 
                'temperature': 0.1, 
                'use_cache': False, 
                'wait_for_model': True,
                'max_tokens': 128000
            }
        })

        if isinstance(output, list) and len(output) > 0 and 'generated_text' in output[0]:
            generated_text = output[0]['generated_text']
            # print(generated_text)
            return generated_text
        else:
            print("No generated text available.")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


DESCRIPTION_PROMPT = """
You are a code analyst and you explain how codes work to expert programmers.
Examine the given commit diff file and give such a programmer a detailed description of it's operation.

Diff file:
```
{diff}
```
"""

CLASSIFYING_PROMPT = """
You are a security evaluator, tasked with analysing code changes to identify their impact on system security.
The provided diff file below was previously run for such security testing, which did not find any issue with the code.
Based on the changes in this diff file, concentrating solely on the lines that start with '+' or '-' and it's description, is it worth re-running the security testing on the modified file?

You should only respond with two strings separated by a semicolon as described below.
The first string should be one of the following: 'yes' (if re-running the security tests on the given diff file is necessary), 'no' (if re-running the security tests on the given diff file is not worth it).
The second string should provide a detailed explanation for your answer. If re-running is not worth it, explain why.

Example response:
"yes; The changes affect critical components that are essential for system security."

Provide your answer only in the specified format above, without any additional text.

The diff file:
```
{diff}

```

The diff file's description (if there's any):
```
{description}
```

Important that testing is a costly operation.
Determine the answer considering the immediate implications of the changes on system security, especially for modifications to critical components.
"""


# Initializing prompt templates
describe_prompt = PromptTemplate(
    template=DESCRIPTION_PROMPT,
    input_variables=["diff"]
)

classify_prompt = PromptTemplate(
    template=CLASSIFYING_PROMPT,
    input_variables=["diff", "description"]
)


# Initializing log time and statistics
current_time = int(time.time())
category_stats = defaultdict(lambda: {'count': 0})


# Logging basic information into txt logs
with open(f"Logs/multi_shot/{REPO}/{RUN_TYPE}/{MODEL.split('/')[0]}/txt_logs/{MODEL.split('/')[1]}_{current_time}.txt", "a") as log_file:
    log_file.write(f"File: {REPO}, pull request #{PR_NUM}\n"
                   f"Model: {MODEL}\n\n")


# Preparing csv logs   
header = ['Repo', 'PR', 'Model', 'Diff number', 'Category', 'Class label', 'Output', 'Stat', 'Reason']

csv_rows = []
csv_row = []
csv_row.append(REPO)
csv_row.append(PR_NUM)
csv_row.append(MODEL)

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
diff_index = 0
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
                    diff_index += 1
                    diff = file['diff_file']
                    
                    unnecessary_diff = remove_unnecessary_diff(path, diff)
                    if unnecessary_diff:
                        print(str(diff_index) + '. diff was removed')
                        continue

                    csv_row.append(diff_index)
                    csv_row.append(label_categories[diff_index - 1][1]) # Category of the diff
                    csv_row.append(label_categories[diff_index - 1][0]) # Class label of the diff

                    try:
                        diff_prompt = describe_prompt.format(diff=diff)
                        # print(diff_prompt)
                        description = generate_text(diff_prompt)
                        print(description)
                        # description = pipeline(diff_prompt)
                        # description = llm.invoke(diff_prompt).content

                        re_run_prompt = classify_prompt.format(diff=diff, description=description)
                        # print(re_run_prompt)
                        re_run_response = generate_text(re_run_prompt)
                        # re_run_response = pipeline(re_run_prompt)
                        # re_run_response = llm.invoke(re_run_prompt).content
                        
                        try:
                            print(re_run_response)
                            output = re_run_response.split(';')[0].lower().strip()
                            reason = re_run_response.split(';')[1].strip()
                        except:
                            print('invalid output was given - ' + str(diff_index) + '. diff was removed')
                            csv_row = csv_row[:3]
                            continue

                        if 'yes' in output:
                            label = 'security'
                        else:
                            label = 'not'
                        
                        csv_row.append(label)
                   
                        # Update counts and total ratings for each category
                        category_stats[label]['count'] += 1

                        # Log input and output
                        with open(f"Logs/multi_shot/{REPO}/{RUN_TYPE}/{MODEL.split('/')[0]}/txt_logs/{MODEL.split('/')[1]}_{current_time}.txt", "a") as log_file:
                            log_file.write(f"Diff number: {diff_index}\nInput 1:{diff_prompt}\nOutput 1:\n{description}\n\n"
                                           f"Input 2:{re_run_prompt}\nOutput 2:\n{re_run_response}\n\n")
                        
                        if repo_name == 'storm':
                            labels = storm_labels()
                        else:
                            labels = struts_labels()
                        
                        if labels[diff_index] == 'security':
                            if label == 'security':
                                exact += 1
                                stat['tp'] += 1
                                csv_row.append('TP')
                            else:
                                stat['fn'] += 1
                                csv_row.append('FN')

                        if labels[diff_index] == 'not':
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

                        print(diff_index)
                        processed_diffs += 1

                    except Exception as e:
                        print("couldn't process - ", e)
                        csv_row = csv_row[:3]
                        continue


# Calculating error number
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
with open(f"Logs/multi_shot/{REPO}/{RUN_TYPE}/{MODEL.split('/')[0]}/csv_logs/{MODEL.split('/')[1]}_{current_time}.csv", "w", newline='') as file:
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
with open(f"Logs/multi_shot/{REPO}/{RUN_TYPE}/{MODEL.split('/')[0]}/txt_logs/{MODEL.split('/')[1]}_{current_time}.txt", "a") as log_file:
    log_file.write(f"Number of diff files: {diff_index}\n"
                   f"Number of processed files: {processed_diffs}\n"
                   f"Statistics: {result_stat}\n"
                   f"Error number: {error_num}\n"
                   f"Accuracy: {accuracy}\n"
                   f"Precision: {precision}\n"
                   f"Recall: {recall}\n"
                   f"F1 Score: {f1_score}")
