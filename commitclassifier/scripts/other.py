import os
import requests


API_TOKEN = os.getenv('API_TOKEN')
url = "https://gcy2v8knprd9c16i.us-east-1.aws.endpoints.huggingface.cloud"

headers = {
    "Accept" : "application/json",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_TOKEN}"
}

data = {
    "inputs": "What is the capital of France?",
    "parameters": {
        'return_full_text': False,
        'temperature': 0.1, 
        'use_cache': False, 
        'wait_for_model': True,
        'max_tokens': 2500
    }
}

response = requests.post(url, headers=headers, json=data)
print(response.json()[0]['generated_text'])
