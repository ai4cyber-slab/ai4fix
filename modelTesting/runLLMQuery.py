import openai
import time

def generate_text(input_text, retries=3, wait=5):
    for attempt in range(retries):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a software developer tasked with writing a patch for the following vulnerability."},
                    {"role": "user", "content": input_text}
                ]
            )
            return response['choices'][0]['message']['content']
        except openai.error.APIError as e:
            if e.http_status == 524:
                print(f"Attempt {attempt + 1}/{retries} failed with error: {e}. Retrying in {wait} seconds...")
                time.sleep(wait)
            else:
                raise e
    raise Exception("Failed to get a response after several retries")