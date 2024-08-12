import os
import json
import time
from scripts.labels import se_labels
from pydantic import BaseModel, Field
from collections import defaultdict
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from finding_relevant_classes import *
from langchain.output_parsers import PydanticOutputParser
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import JSONLoader
from langchain_community.document_loaders import GitLoader


PR_NUM = 448
REPO = 'storm'
TEMPERATURE = 0
GPT_MODEL = 'gpt-3.5-turbo-0125'
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

PROMPT = """You are a security evaluator, tasked with analyzing code changes to identify their impact on system security.
Your focus should be on detecting modifications that directly affect critical security components such as authentication mechanisms, encryption algorithms, access control procedures, and logging levels related to security events.
Please review the provided diff file, concentrating solely on the lines that start with '+' or '-'.
Your analysis should discern whether these changes are directly related to security functionalities, could potentially impact the system's security, or are unrelated to security concerns.
Your analysis must accurately categorize the security relevance of the diff file, offering a clear rationale for your classification and indicating your confidence level in your assessment.
Consider the immediate implications of the changes on system security, especially for modifications to critical components.
You will be given multiple diff files similar to the one you will analyse.
If there is any, you will also be given a source diff file that is related to the original diff file.
It is either the class of the original diff file, or it is another class, where the original diff file is called.
Use these extra contexts for your evaluation.
{format_instructions}
Diff file:
```
{code_snippet}
```
Similar diff files:
```
{context}
```
Source file:
```
{source}
```
Analyse the changes with a critical eye towards their impact on the security posture of the system, paying close attention to how they might alter authentication flows, data protection mechanisms, or the security of communications.
Your goal is to provide a nuanced and thorough evaluation that helps in understanding the security implications of the code changes presented."""


class Output(BaseModel):
    security_relevancy: str = Field(
        description="A string whose value is one of the following: "
                    "['security_relevant' (if the code directly impacts security functionalities), "
                    "'potentially_security_relevant' (if the changes could impact the system's security but require further analysis), "
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
    input_variables=["code_snippet", "source", "context"],
    partial_variables={"format_instructions": format_instructions},
)


# Loading java classes
loader = GitLoader(
    repo_path=f"repo_clones/{REPO}",
    file_filter=lambda file_path: file_path.endswith(".java"),
    branch="master"
)
java_files = loader.load()


# RAG
embeddings_model = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

loader = JSONLoader(
    file_path=f'final_jsons/{REPO}.json',
    jq_schema='.pulls[].commits[].files[]',
    content_key="diff_file",
    text_content=False
)

data = loader.load()
del data[:2] # Deleting the those diff files, that are from another pull request.
db = Chroma.from_documents(data, embeddings_model)


# Initializing statistics
current_time = int(time.time())
category_stats = defaultdict(lambda: {'count': 0, 'total_confidence': 0})


# Log basic information
with open(f"testing_with_gpt/Non_RAG/logs_with_called_classes/{REPO}_{GPT_MODEL}_{current_time}.txt", "a") as log_file:
    log_file.write(f"File: {REPO}, pull request #{PR_NUM}\n"
                   f"Model: {GPT_MODEL}\n\n")


# Inference
index = 0
exact = 0
number_of_diffs = 0
labels = se_labels()
folder_path = 'final_jsons'
number_of_called_classes = 0

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
                    number_of_diffs += 1
                    diff = file['diff_file']
                    context = ''

                    try:
                        called_class = find_called_class(diff, java_files)

                        if called_class != '':
                            number_of_called_classes += 1
                        
                        embedded_query = embeddings_model.embed_query(diff)
                        docs = db.similarity_search_by_vector(embedded_query)

                        for doc in docs:
                            if doc.page_content != diff:
                                context += doc.page_content

                        try:
                            prompt = prompt_template.format(code_snippet=diff, source=called_class, context=context)
                            response = llm.invoke(prompt)
                            parsed_output = parser.parse(response.content)
                        except:
                            prompt = prompt_template.format(code_snippet=diff, source='', context=context)
                            response = llm.invoke(prompt)
                            parsed_output = parser.parse(response.content)

                        # Extract relevant attributes
                        sec_rel = parsed_output.security_relevancy

                        # Update counts and total ratings for each category
                        category_stats[sec_rel]['count'] += 1
                        category_stats[sec_rel]['total_confidence'] += parsed_output.confidence

                        # Log input and output
                        with open(f"testing_with_gpt/Non_RAG/logs_with_called_classes/{REPO}_{GPT_MODEL}_{current_time}.txt", "a") as log_file:
                            log_file.write(f"Input: {prompt}\n\nOutput: {response.content}\n\n")

                        index += 1
                        print(index)

                        if sec_rel.split('_')[0] == labels[index]:
                            exact += 1
                    except Exception as e:
                        print("couldn't process", e)
                        continue


# Calculate mean confidence for each category
se = {'security_relevant': 26, 'potentially_security_relevant': 8, 'not_security_relevant': 11}
error_num = 0

result_stat = []
for category, stats in category_stats.items():
    count = stats['count']
    total_confidence = stats['total_confidence']
    mean_confidence = total_confidence // count if count > 0 else 0
    
    result_stat.append({
        category: count,
        'mean': mean_confidence
    })

    error_num += abs(se[category] - count)


# Logging statistics
with open(f"testing_with_gpt/Non_RAG/logs_with_called_classes/{REPO}_{GPT_MODEL}_{current_time}.txt", "a") as log_file:
    log_file.write(f"Number of diff files: {number_of_diffs}\n"
                   f"Number of processed files: {index}\n"
                   f"number of called classes: {number_of_called_classes}\n"
                   f"Statistics: {result_stat}\n"
                   f"Error number: {error_num}\n"
                   f"Succes rate: {exact/index * 100}")
