import re
import sys

from groq import Groq
from openai import OpenAI, AzureOpenAI
from anthropic import Anthropic
from utils.logger import logger


def llm_response(provider, model, api_key, messages, endpoint=None, api_v=None):
    try:
        if provider.lower() == 'openai':
            return client_response(OpenAI(api_key=api_key), model, messages)
        elif provider.lower() == 'deepseek':
            return client_response(OpenAI(api_key=api_key, base_url="https://api.deepseek.com"), model, messages)
        elif provider.lower() == 'azureopenai':
            return client_response(AzureOpenAI(api_key=api_key, azure_endpoint=endpoint, api_version=api_v), model, messages)
        elif provider.lower() == 'groq':
            return client_response(Groq(api_key=api_key), model, messages)
        elif provider.lower() == 'claude':
            client = Anthropic(
                api_key=api_key,
            )
            response = client.messages.create(
                model=model,
                max_tokens=6000,
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
        match = re.search(r"'message': '([^']*)'", str(e))
        if match:
            message = match.group(1)
        logger.error(f'An error occured while initializing the LLM: {message if message != "" else e}')
        sys.exit(1)


def client_response(client, model, messages):
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
        )
        # Validate the structure of the response
        if not response.choices or not response.choices[0].message:
            print(f"The LLM couldn't provide a valid response. Response:\n{response}")
            sys.exit(1)

        # Extract response content safely
        message_content = response.choices[0].message.content

        # Validate and extract token usage
        input_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') else 0
        output_tokens = response.usage.completion_tokens if hasattr(response, 'usage') else 0

        return {
            'message': message_content,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
        }

    except Exception as e:
        logger.error(f"Error in client_response: {e}")
        sys.exit(1)