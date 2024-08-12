import os
import time
from pydantic import BaseModel, Field
from collections import defaultdict
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from scripts.finding_relevant_classes import find_relevant_java_class
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import GitLoader
from langchain_community.document_loaders import JSONLoader


REPO = 'storm'
PR = 448
GPT_MODEL = 'gpt-4-0125-preview'
TEMPERATURE = 0
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

PROMPT = """You are a security evaluator, tasked with analyzing code changes to identify their impact on system security.
Your focus should be on detecting modifications that directly affect critical security components such as authentication mechanisms, encryption algorithms, access control procedures, and logging levels related to security events.
Please review the provided diff files, concentrating solely on the lines that start with '+' or '-'.
Your analysis should discern whether the changes in these diff files are directly related to security functionalities, could potentially impact the system's security, or are unrelated to security concerns.
Your analysis must accurately categorize the security relevance of each diff file, offering a clear rationale for your classification and indicating your confidence level in your assessment.
Consider the immediate implications of the changes on system security, especially for modifications to critical components.
The diff files are related to each other, and for a bigger context, you will also be provided with the relevant java classes of the diff files (if there's any), which should be taken into consideration when providing your assessment.
Each diff file starts with 'diff --git'. Separate them accordingly, and provide an evaluation for all of them.
{format_instructions}
Below is the history of the formal requests, stored in a dictionary. The keys are category names for each diff file, and their values are the labels you provided for them.
Compare the given diff files to your previous assessments, before providing your evaluation.
History:
```
{history}
```
Diff files:
```
{code_snippet}
```
Relevant java class(es):
```
{java_classes}
```
Analyze the changes with a critical eye towards their impact on the security posture of the system, paying close attention to how they might alter authentication flows, data protection mechanisms, or the security of communications.
Your goal is to provide a nuanced and thorough evaluation that helps in understanding the security implications of the code changes presented."""


class Output(BaseModel):
    security_relevancy: str = Field(
        description="A string whose value is one of the following: "
                    "['security_relevant' (if the code directly impacts security functionalities), "
                    "'potenitally_security_relevant' (if the changes could impact the system's security, but require further analysis), "
                    "'not_security_relevant' (if the changes do not involve security functionalities)].")
    reason: str = Field(
        description="Provide a detailed explanation for your classification. "
                    "If the changes are not related to security, explain why.")
    confidence: int = Field(
        description="Rate your confidence in your assessment from 0-10, "
                    "with 0 being not confident and 10 being extremely confident.")
    category: str = Field(
        description="Give a one word category for the changes in each diff file "
                    "(what it is about, what it's main focus)")
    

class OutputBase(BaseModel):
    output: list[Output] = []


# Initializing the LLM
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=TEMPERATURE, model_name=GPT_MODEL)

parser = PydanticOutputParser(pydantic_object=OutputBase)
format_instructions = parser.get_format_instructions()
prompt_template = PromptTemplate(
    template=PROMPT,
    input_variables=["history", "code_snippet", "java_classes"],
    partial_variables={"format_instructions": format_instructions},
)


# RAG
embeddings_model = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

loader = JSONLoader(
    file_path=f'final_jsons/{REPO}.json',
    jq_schema='.pulls[].commits[].files[].diff_file',
    text_content=False
)

data = loader.load()
# del data[:21], data[-10:] # Deleting the those diff files, that are from another pull request.
del data[:2]
ids = [str(i) for i in range(1, len(data) + 1)]
db = Chroma.from_documents(data, embeddings_model, ids=ids)

groups = []
while len(data) != 0:
    for diff in data:
        diffs = []
        embedded_query = embeddings_model.embed_query(diff.page_content)
        docs = db.similarity_search_by_vector(embedded_query)
        groups.append(docs)
        for doc in docs:
            diffs.append(doc.page_content)
        break

    data = [diff for diff in data if diff not in docs]
    for id in ids:
        if db._collection.get(ids=id)['ids'] != []:
            if db._collection.get(ids=id)['documents'][0] in diffs:
                db._collection.delete(ids=id)
    

# Initializing statistics
current_time = int(time.time())
category_stats = defaultdict(lambda: {'count': 0, 'total_confidence': 0})


# Log basic information
with open(f"testing_with_gpt/rag_logs_with_source/{REPO}_{GPT_MODEL}_{current_time}.txt", "a") as log_file:
    log_file.write(f"File: {REPO}.json, pull request {PR}\n"
                   f"Model: {GPT_MODEL}\n\n")


# Loading java classes
loader = GitLoader(
    repo_path=f"repo_clones/{REPO}",
    file_filter=lambda file_path: file_path.endswith(".java"),
    branch="master"
)
java_files = loader.load()


# Inference
index = 0
history = dict()
min_class = 1
for group in groups:
    try:
        diffs = ''
        classes = set()
        for doc in group:
            diff = doc.page_content
            diffs += diff
            class_code = find_relevant_java_class(diff, java_files)
            if class_code != '':
                classes.add(class_code)

        java_classes = ''
        if len(classes) != 0:
            for java_class in classes:
                java_classes += java_class
        
        long = True
        while long:
            try:
                prompt = prompt_template.format(history=history, code_snippet=diffs, java_classes=java_classes)
                response = llm.invoke(prompt)
                parsed_output = parser.parse(response.content)
                long = False
            except:
                dif = len(classes) - min_class
                java_classes = ''
                if len(classes) != 0 and dif > 0:
                    classes = list(classes)
                    for i in range(0, dif):
                        java_classes += classes[i]
                min_class += 1

        for output in parsed_output:
            for i in range(0, len(output[1])):
                sec_rel = output[1][i].security_relevancy
                cat = output[1][i].category
                history[cat] = sec_rel

                # Update counts and total confidence for each category
                category_stats[sec_rel]['count'] += 1
                category_stats[sec_rel]['total_confidence'] += output[1][i].confidence

        # Log input and output
        with open(f"testing_with_gpt/rag_logs_with_source/{REPO}_{GPT_MODEL}_{current_time}.txt", "a") as log_file:
            log_file.write(f"Input: {prompt}\n\nOutput: {response.content}\n\n")

        index += 1
        print(index)

    except Exception as e:
        print("couldn't process")
        print(e)
        break


# Calculate mean confidence for each category
result_stat = []
for category, stats in category_stats.items():
    count = stats['count']
    total_confidence = stats['total_confidence']
    mean_confidence = total_confidence // count if count > 0 else 0
    
    result_stat.append({
        category: count,
        'mean': mean_confidence
    })


# Logging statistics
with open(f"testing_with_gpt/rag_logs_with_source/{REPO}_{GPT_MODEL}_{current_time}.txt", "a") as log_file:
    log_file.write(f"Number of diff file groups: {len(groups)}\n"
                   f"Number of processed groups: {index}\n"
                   f"Statistics: {result_stat}")
