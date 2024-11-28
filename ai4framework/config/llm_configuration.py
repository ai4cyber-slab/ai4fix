import sys

from groq import Groq
from openai import OpenAI
from anthropic import Anthropic


def llm_response(provider, model, api_key, messages):
    try:
        if provider == 'openai':
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
            )
            return {
                'message': response.choices[0].message.content,
                'input_tokens': response.usage.prompt_tokens,
                'output_tokens': response.usage.completion_tokens
            }
        elif provider == 'groq':
            client = Groq(
                api_key=api_key,
            )
            response = client.chat.completions.create(
                messages=messages,
                model=model,
            )
            return {
                'message': response.choices[0].message.content,
                'input_tokens': response.usage.prompt_tokens,
                'output_tokens': response.usage.completion_tokens
            }
        elif provider == 'claude':
            client = Anthropic(
                api_key=api_key,
            )
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=messages,
            )
            return {
                'message': response.content.text,
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens
            }
        else:
            print("Couldn't find provider. Please check in the configuration.")
            sys.exit(1)
    except Exception as e:  
        print(f'An error occured while initializing the LLM: {e}')
        sys.exit(1)
