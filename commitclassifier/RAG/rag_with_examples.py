import os
import time
import json
from pydantic import BaseModel, Field
from collections import defaultdict
from scripts.labels import *
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import JSONLoader


REPO = 'struts'
PR_NUM = 252
GPT_MODEL = 'gpt-3.5-turbo-0125'
TEMPERATURE = 0
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')


# Define the metadata extraction function.
def metadata_func(record: dict, metadata: dict) -> dict:

    metadata["security_relevancy"] = record.get("security_relevancy")

    return metadata


PROMPT = """You are a security evaluator, tasked with analyzing code changes to identify their impact on system security.
Your focus should be on detecting modifications that directly affect critical security components such as authentication mechanisms, encryption algorithms, access control procedures, and logging levels related to security events.
Please review the provided diff file, concentrating solely on the lines that start with '+' or '-'.
Your analysis should discern whether the changes in this diff file are directly related to security functionalities, could potentially impact the system's security, or are unrelated to security concerns.
Your analysis must accurately categorize the security relevance of the diff file, offering a clear rationale for your classification and indicating your confidence level in your assessment.
Consider the immediate implications of the changes on system security, especially for modifications to critical components.
For example, the following are not related to security functionalities: creating or working with interfaces, making changes related to test functions, and creating test classes, among others.
You will also be given a context containing diff files similar to the one you will analyse.
Use this context for your evaluation.
{format_instructions}
Diff file:
```
{code_snippet}
```
Context:
```
{context}
```
Analyze the changes with a critical eye towards their impact on the security posture of the system, paying close attention to how they might alter authentication flows, data protection mechanisms, or the security of communications.
Your goal is to provide a nuanced and thorough evaluation that helps in understanding the security implications of the code changes presented."""


class Output(BaseModel):
    security_relevancy: str = Field(
        description="A string whose value is one of the following: "
                    "['security_relevant' (if the code directly impacts security functionalities), "
                    "'not_security_relevant' (if the changes do not involve security functionalities)].")
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


# RAG
embeddings_model = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

loader = JSONLoader(
    file_path=f'original_json_files/{REPO}.json',
    jq_schema='.pulls[].commits[].files[]',
    content_key="diff_file",
    text_content=False
)

data = loader.load()
del data[:21], data[-10:]
db = Chroma.from_documents(data, embeddings_model)


# Initializing statistics
current_time = int(time.time())
category_stats = defaultdict(lambda: {'count': 0, 'total_confidence': 0})


# Inference
index = 0
exact = 0
number_of_diffs = 0
processed_diffs = 0
labels = struts_labels()
folder_path = 'original_json_files'
stat = {'tp': 0, 'tn': 0, 'fp': 0, 'fn': 0}

for filename in os.listdir(folder_path):

    file_path = os.path.join(folder_path, filename)

    if filename.endswith(f"{REPO}.json"):
        # Process the JSON file
        with open(file_path, 'r') as file:
            data = json.load(file)
    else:
        continue

    for pull in data['pulls']:
        if pull['number'] == PR_NUM:
            for commit in pull['commits']:

                for file in commit['files']:
                    index += 1
                    number_of_diffs += 1
                    diff = file['diff_file']
                    similar_diffs = ''
                    try:
                        embedded_query = embeddings_model.embed_query(diff)
                        docs = db.similarity_search_by_vector(embedded_query)

                        for doc in docs:
                            if doc.page_content != diff:
                                similar_diffs += doc.page_content

                        prompt = prompt_template.format(code_snippet=diff, context=similar_diffs)
                        response = llm.invoke(prompt)

                        # Extract relevant attributes
                        parsed_output = parser.parse(response.content)
                        sec_rel = parsed_output.security_relevancy
                        label = sec_rel.split('_')[0]

                        # Update counts and total ratings for each category
                        category_stats[label]['count'] += 1
                        category_stats[label]['total_confidence'] += parsed_output.confidence

                        # Log input and output
                        with open(f"FEA/{REPO}/updated_prompt/2_label/txt_logs/context_is_similar_diffs/{GPT_MODEL}_{current_time}.txt", "a") as log_file:
                            log_file.write(f"Diff number: {index}\nInput: {prompt}\n\nOutput: {response.content}\n\n")
                        

                        if labels[index] == 'security':
                            if label == 'security':
                                exact += 1
                                stat['tp'] += 1
                            else:
                                stat['fn'] += 1

                        if labels[index] == 'potentially':
                            exact += 1
                            if label == 'security':
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
        'mean': mean_confidence
    })

    error_num += abs(struts_stat[catetgory] - count)


# Statistics
accuracy = exact/processed_diffs
precision = stat['tp']/(stat['tp'] + stat['tn'])
recall = stat['tp']/(stat['tp'] + stat['fn'])
f1_score = 2*precision*recall/(precision + recall)

# Logging statistics
with open(f"FEA/{REPO}/updated_prompt/2_label/txt_logs/context_is_similar_diffs/{GPT_MODEL}_{current_time}.txt", "a") as log_file:
    log_file.write(f"Number of diff files: {number_of_diffs}\n"
                   f"Number of processed files: {processed_diffs}\n"
                   f"Statistics: {result_stat}\n"
                   f"Error number: {error_num}\n"
                   f"Accuracy: {accuracy}\n"
                   f"Precision: {precision}\n"
                   f"Recall: {recall}\n"
                   f"F1 Score: {f1_score}")



