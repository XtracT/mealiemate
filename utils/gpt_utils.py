"""
Module: gpt_utils
-----------------
Provides a unified interface for calling OpenAI's Chat Completions API with JSON response format.
This module handles authentication, error handling, and response parsing.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration for API providers
USE_OPENROUTER = os.getenv("USE_OPENROUTER", "").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-r1-zero:free")
SELECTED_MODEL = OPENROUTER_MODEL if USE_OPENROUTER else OPENAI_MODEL

# Validate API keys
if USE_OPENROUTER:
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY is required when using OpenRouter")
else:
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not found in environment variables")

# Create appropriate client configuration
if USE_OPENROUTER:
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
else:
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def gpt_json_chat(
    messages: List[Dict[str, str]], 
    temperature: float = 0.1,
    max_retries: int = 2,
    retry_delay: float = 1.0
) -> Dict[str, Any]:
    """
    Sends a series of messages to AI provider with JSON output and
    returns a Python dict if JSON can be parsed, or an empty dict on failure.

    Args:
        messages: List of {"role": "...", "content": "..."} chat messages
        temperature: Completion temperature (0.0 to 2.0)
        max_retries: Max retry attempts on transient errors
        retry_delay: Delay between retries in seconds
        
    Returns:
        Parsed JSON response as dictionary or empty dict on failure
    """
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            logger.info(f"Sending request to {SELECTED_MODEL} via {'OpenRouter' if USE_OPENROUTER else 'OpenAI'}")
            
            params = {
                "model": SELECTED_MODEL,
                "messages": messages,
                "temperature": temperature,
                "response_format": {"type": "json_object"}
            }

            if USE_OPENROUTER:
                params["extra_headers"] = {
                    "HTTP-Referer": "https://github.com/mealiemate/mealiemate",
                    "X-Title": "MealieMate"
                }

            completion = await client.chat.completions.create(**params)
            raw_output = completion.choices[0].message.content
            
            try:
                result = json.loads(raw_output)
                logger.info("Successfully received and parsed JSON response from OpenAI")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from OpenAI response: {str(e)}")
                logger.debug(f"Raw response: {raw_output[:100]}...")
                return {}
                
        except asyncio.CancelledError:
            # Re-raise cancellations so they propagate properly
            logger.warning("Request to OpenAI was cancelled")
            raise
            
        except Exception as e:
            retry_count += 1
            if retry_count <= max_retries:
                logger.warning(f"Error calling OpenAI API: {str(e)}. Retrying ({retry_count}/{max_retries})...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed to get response from OpenAI after {max_retries} retries: {str(e)}")
                return {}
    
    # This should never be reached due to the return in the final else clause above
    return {}
