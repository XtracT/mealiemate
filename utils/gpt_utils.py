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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not found in environment variables")

# Create an AsyncOpenAI client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def gpt_json_chat(
    messages: List[Dict[str, str]], 
    model: str = "gpt-4o", 
    temperature: float = 0.1,
    max_retries: int = 2,
    retry_delay: float = 1.0
) -> Dict[str, Any]:
    """
    Sends a series of messages to OpenAI Chat Completion with JSON output and
    returns a Python dict if JSON can be parsed, or an empty dict on failure.

    Args:
        messages: A list of {"role": "...", "content": "..."} chat messages
        model: Which model to use (e.g. "gpt-4o")
        temperature: The temperature for the completion (0.0 to 2.0)
        max_retries: Maximum number of retry attempts on transient errors
        retry_delay: Delay between retries in seconds
        
    Returns:
        Parsed JSON response as dictionary or empty dict on failure
    """
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            logger.info(f"Sending request to OpenAI API using model: {model}")
            completion = await client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},  # instruct OpenAI to respond with valid JSON
                messages=messages,
                temperature=temperature
            )
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
