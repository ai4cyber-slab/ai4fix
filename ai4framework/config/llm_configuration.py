import sys

from groq import Groq
from openai import OpenAI
from anthropic import Anthropic
from utils.logger import logger


def llm_response(provider, model, api_key, messages):
    try:
        if provider.lower() == 'openai':
            return client_response(OpenAI(api_key=api_key), model, messages)
        elif provider.lower() == 'groq':
            return client_response(Groq(api_key=api_key), model, messages)
        elif provider.lower() == 'claude':
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
            logger.error("Couldn't find provider. Please check in the configuration.")
            sys.exit(1)
    except Exception as e:  
        logger.error(f'An error occured while initializing the LLM: {e}')
        sys.exit(1)


def client_response(client, model, messages):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    return {
        'message': response.choices[0].message.content,
        'input_tokens': response.usage.prompt_tokens,
        'output_tokens': response.usage.completion_tokens
    }
