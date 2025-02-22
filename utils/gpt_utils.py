"""
Module: gpt_utils
-----------------
Provides a unified interface for calling OpenAI's Chat Completions, returning JSON.
"""

import os
import json
from dotenv import load_dotenv
from openai import AsyncOpenAI
import asyncio

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Create an AsyncOpenAI client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def gpt_json_chat(messages, model="gpt-4o", temperature=0.1):
    """
    Sends a series of messages to OpenAI Chat Completion with JSON output and
    returns a Python dict if JSON can be parsed, or an empty dict on failure.

    :param messages: A list of {"role": "...", "content": "..."} chat messages.
    :param model: Which model to use (e.g. "gpt-4o").
    :param temperature: The temperature for the completion.
    :return: Parsed JSON (dict) or {} if JSON decoding fails.
    """
    try:
        completion = await client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},  # instruct OpenAI to respond with valid JSON
            messages=messages,
            temperature=temperature
        )
        raw_output = completion.choices[0].message.content
        return json.loads(raw_output)
    except json.JSONDecodeError:
        return {}
    except asyncio.CancelledError:
        # Re-raise cancellations so they propagate properly
        raise
    except Exception:
        # If anything else goes wrong, return empty dict
        return {}
