import os
import time
import json
from collections import defaultdict
from langchain_openai import OpenAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import JSONLoader


REPO = 'storm'
PR_NUM = 448
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')


# RAG
embeddings_model = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

loader = JSONLoader(
    file_path='testing_with_gpt/all_storm_commits.json',
    jq_schema='.commits[].files[]',
    content_key="diff",
    text_content=False
)

data = loader.load()
db = Chroma.from_documents(data, embeddings_model)


# Initializing statistics
current_time = int(time.time())
category_stats = defaultdict(lambda: {'count': 0, 'total_confidence': 0})


# Inference
index = 1
context = []
diffs = set()
res_json = dict()
number_of_diffs = 0
folder_path = 'final_jsons'

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
                    try:
                        embedded_query = embeddings_model.embed_query(diff)
                        docs = db.similarity_search_by_vector(embedded_query)

                        for doc in docs:
                            diffs.add(doc.page_content)

                        print(index)
                        index += 1

                    except Exception as e:
                        print("couldn't process", e)
                        continue


for diff in diffs:
    context.append({'diff': diff, 'security_relevancy': ''})

res_json['diff_files'] = context

with open(f'testing_with_gpt/RAG/rag_with_examples_logs/{REPO}_{current_time}.json', 'w') as file:
    json.dump(res_json, file)
