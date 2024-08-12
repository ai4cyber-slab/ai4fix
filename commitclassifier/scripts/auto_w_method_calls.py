import os
import time
import json
from labels import *
from pydantic import BaseModel, Field
from collections import defaultdict
from diff_filtering import *
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from extract_diff_methods import *
from langchain.output_parsers import PydanticOutputParser


REPO_1 = 'storm'
REPO_2 = 'struts'
PR_NUM_1 = 448
PR_NUM_2 = 252
LABEL_NUM = 4
GPT_MODEL = 'gpt-3.5-turbo-0125'
TEMPERATURE = 0
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')


PROMPT = """You are a security evaluator, tasked with analyzing code changes to identify their impact on system security.
Your focus should be on detecting modifications that directly affect critical security components such as authentication mechanisms, encryption algorithms, access control procedures, and logging levels related to security events.
Please review the provided diff file, concentrating solely on the lines that start with '+' or '-'.
Your analysis should discern whether the changes in this diff file are directly related to security functionalities or are unrelated to security concerns.
Your analysis must accurately categorize the security relevance of the diff file, offering a clear rationale for your classification and indicating your confidence level in your assessment.
Consider the immediate implications of the changes on system security, especially for modifications to critical components.
{format_instructions}
You will also receive context containing class(es) where the methods in the diff file were called. If no methods are present in the diff file, this context will be empty.
Use this extra information for your evaluation.
Diff file:
```
{code_snippet}
```
Context:
```
{context}
```
Analyse the changes with a critical eye towards their impact on the security posture of the system, paying close attention to how they might alter authentication flows, data protection mechanisms, or the security of communications.
Your goal is to provide a nuanced and thorough evaluation that helps in understanding the security implications of the code changes presented."""


class Output(BaseModel):
    security_relevancy: str = Field(
        description="A string whose value is one of the following: "
                    "['security_relevant' (if the code directly impacts security functionalities), "
                    "'potentially_security_relevant' (if the changes could impact the security of the system but require further analysis), "
                    "'potentially_not_security_relevant' (if the changes are likely not related to security functionalities), "
                    "'not_security_relevant' (if the changes do not involve any security functionalities)].")
    reason: str = Field(
        description="Provide a detailed explanation for your classification. "
                    "If the changes are not related to security, explain why.")
    confidence: int = Field(
        description="Rate your confidence in your assessment from 0-10, "
                    "with 0 being not confident and 10 being extremely confident.")


# Initializing the LLM
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=TEMPERATURE, model_name=GPT_MODEL)

parser = PydanticOutputParser(pydantic_object=Output)
format_instructions = parser.get_format_instructions()
prompt_template = PromptTemplate(
    template=PROMPT,
    input_variables=["code_snippet", "context"],
    partial_variables={"format_instructions": format_instructions},
)


# Initializing log time
current_time = int(time.time())
category_stats = defaultdict(lambda: {'count': 0, 'total_confidence': 0})


# Log basic information
with open(f"Logs/w_method_calls/{REPO_1}/{LABEL_NUM}_label/txt_logs/{GPT_MODEL}_{current_time}.txt", "a") as log_file:
    log_file.write(f"File: {REPO_1}, pull request #{PR_NUM_1}\n"
                   f"Model: {GPT_MODEL}\n\n")
    

# Inference
exact = 0
processed_diffs = 0
number_of_diffs = 0
folder_path = 'original_json_files'
stat = {'tp': 0, 'tn': 0, 'fp': 0, 'fn': 0}

for filename in os.listdir(folder_path):
    
    index = 0
    file_path = os.path.join(folder_path, filename)

    if filename.endswith(f"{REPO_1}.json"):
        repo_name = REPO_1
        pr = PR_NUM_1
        path = f'original_cloned_repos/{REPO_1}'

        # Process the JSON file
        with open(file_path, 'r') as file:
            data = json.load(file)

    # elif filename.endswith(f"{REPO_2}.json"):
        # repo_name = REPO_2
        # pr = PR_NUM_2
        # path = f'original_cloned_repos/{REPO_2}'

        # with open(file_path, 'r') as file:
            # data = json.load(file)
    else:
        continue

    for pull in data['pulls']:
        if pull['number'] == pr:

            # print(repo_name)
            # with open(f"Logs/w_method_calls/{REPO_1}+{REPO_2}/{LABEL_NUM}_label/txt_logs/{GPT_MODEL}_{current_time}.txt", "a") as log_file:
                # log_file.write(f"Repo: {repo_name}\n\n")

            for commit in pull['commits']:

                for file in commit['files']:
                    index += 1
                    number_of_diffs += 1
                    diff = file['diff_file']

                    diff_method_names = diff_methods(diff)
                    context = find_method_calls(path, diff_method_names)
                    try:
            
                        prompt = prompt_template.format(code_snippet=diff, context=context)
                        response = llm.invoke(prompt)

                        # Extract relevant attributes
                        parsed_output = parser.parse(response.content)
                        sec_rel = parsed_output.security_relevancy
                        if sec_rel == 'potentially_security_relevant':
                            label = 'potentially_security'
                        elif sec_rel == 'potentially_not_security_relevant':
                            label = 'potentially_not'
                        else:
                            label = sec_rel.split('_')[0]

                        # Update counts and total ratings for each category
                        category_stats[label]['count'] += 1
                        category_stats[label]['total_confidence'] += parsed_output.confidence

                        # Log input and output
                        with open(f"Logs/w_method_calls/{REPO_1}/{LABEL_NUM}_label/txt_logs/{GPT_MODEL}_{current_time}.txt", "a") as log_file:
                            log_file.write(f"Diff number: {index}\nInput: {prompt}\n\nOutput: {response.content}\n\n")
                        
                        if repo_name == REPO_1:
                            labels = storm_labels()
                        else:
                            labels = struts_labels()
                        
                        if labels[index] == 'security':
                            if label == 'security':
                                exact += 1
                                stat['tp'] += 1
                            else:
                                stat['fn'] += 1

                        if labels[index] == 'potentially':
                            exact += 1
                            if label == 'security' or label == 'potentially_security':
                                stat['tp'] += 1
                            else:
                                stat['tn'] += 1
                            # if label == "security":
                                # stat['tp'] += 1
                            # else:
                                # stat['tn'] += 1

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

    if catetgory == 'potentially_security' or catetgory == 'potentially_not':
        catetgory = 'potentially'
    error_num += abs(storm_stat[catetgory] - count)


# Statistics
accuracy = exact/processed_diffs
precision = stat['tp']/(stat['tp'] + stat['fp'])
recall = stat['tp']/(stat['tp'] + stat['fn'])
f1_score = 2*precision*recall/(precision + recall)

# Logging statistics
with open(f"Logs/w_method_calls/{REPO_1}/{LABEL_NUM}_label/txt_logs/{GPT_MODEL}_{current_time}.txt", "a") as log_file:
    log_file.write(f"Number of diff files: {number_of_diffs}\n"
                   f"Number of processed files: {processed_diffs}\n"
                   f"Statistics: {result_stat}\n"
                   f"Error number: {error_num}\n"
                   f"Accuracy: {accuracy}\n"
                   f"Precision: {precision}\n"
                   f"Recall: {recall}\n"
                   f"F1 Score: {f1_score}")
