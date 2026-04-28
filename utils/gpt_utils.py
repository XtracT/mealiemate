"""
Module: gpt_utils
-----------------
Provides a unified interface for calling OpenRouter's Chat Completions API
with JSON response format.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI, RateLimitError
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-r1-zero:free")

if not OPENROUTER_API_KEY:
    logger.error("OPENROUTER_API_KEY not found in environment variables")

# Mutable runtime state
_model_name: str = DEFAULT_MODEL

# Lazy client singleton
_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
    return _client


def get_model() -> str:
    """Get the currently selected model name."""
    return _model_name


def set_model(model: str) -> None:
    """Set the model name at runtime."""
    global _model_name
    _model_name = model
    logger.info(f"AI model changed to: {model}")


class GptQuotaExceeded(Exception):
    """Raised when the API quota is exhausted and retries won't help."""
    pass


async def gpt_json_chat(
    messages: List[Dict[str, str]], 
    temperature: float = 0.1,
    max_retries: int = 2,
    retry_delay: float = 1.0
) -> Dict[str, Any]:
    """
    Sends a series of messages to OpenRouter with JSON output and
    returns a Python dict if JSON can be parsed, or an empty dict on failure.

    Args:
        messages: List of {"role": "...", "content": "..."} chat messages
        temperature: Completion temperature (0.0 to 2.0)
        max_retries: Max retry attempts on transient errors
        retry_delay: Delay between retries in seconds
        
    Returns:
        Parsed JSON response as dictionary or empty dict on failure
        
    Raises:
        GptQuotaExceeded: If the API quota is exhausted (non-retryable)
    """
    retry_count = 0
    model = _model_name
    client = _get_client()
    
    while retry_count <= max_retries:
        try:
            logger.info(f"Sending request to {model} via OpenRouter")
            
            params = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "response_format": {"type": "json_object"},
                "extra_headers": {
                    "HTTP-Referer": "https://github.com/mealiemate/mealiemate",
                    "X-Title": "MealieMate"
                }
            }

            completion = await client.chat.completions.create(**params)
            raw_output = completion.choices[0].message.content
            
            try:
                result = json.loads(raw_output)
                logger.info("Successfully received and parsed JSON response")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from response: {str(e)}")
                return {}
                
        except asyncio.CancelledError:
            logger.warning("Request to OpenRouter was cancelled")
            raise
            
        except RateLimitError as e:
            error_body = str(e)
            if "insufficient_quota" in error_body:
                logger.error(f"Quota exhausted — not retrying: {str(e)}")
                raise GptQuotaExceeded(f"Quota exhausted: {str(e)}")
            retry_count += 1
            if retry_count <= max_retries:
                logger.warning(f"Rate limited: {str(e)}. Retrying ({retry_count}/{max_retries})...")
                await asyncio.sleep(retry_delay * retry_count)
            else:
                logger.error(f"Failed after {max_retries} retries: {str(e)}")
                return {}
            
        except Exception as e:
            retry_count += 1
            if retry_count <= max_retries:
                logger.warning(f"Error: {str(e)}. Retrying ({retry_count}/{max_retries})...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed after {max_retries} retries: {str(e)}")
                return {}
    
    return {}
