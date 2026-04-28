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
from openai import AsyncOpenAI, RateLimitError
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Default configuration from environment
_DEFAULT_USE_OPENROUTER = os.getenv("USE_OPENROUTER", "").lower() == "true"
_DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
_DEFAULT_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-r1-zero:free")
_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
_OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Validate API keys
if not _DEFAULT_USE_OPENROUTER and not _OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY not found in environment variables")
if _DEFAULT_USE_OPENROUTER and not _OPENROUTER_API_KEY:
    logger.error("OPENROUTER_API_KEY is required when using OpenRouter")

# Mutable runtime state
_use_openrouter: bool = _DEFAULT_USE_OPENROUTER
_model_name: str = _DEFAULT_OPENROUTER_MODEL if _DEFAULT_USE_OPENROUTER else _DEFAULT_OPENAI_MODEL

# Client instances (lazily recreated on provider switch)
_openai_client: Optional[AsyncOpenAI] = None
_openrouter_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    """Get or create the appropriate AsyncOpenAI client."""
    global _openai_client, _openrouter_client
    if _use_openrouter:
        if _openrouter_client is None:
            _openrouter_client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=_OPENROUTER_API_KEY,
            )
        return _openrouter_client
    else:
        if _openai_client is None:
            _openai_client = AsyncOpenAI(api_key=_OPENAI_API_KEY)
        return _openai_client


def get_model() -> str:
    """Get the currently selected model name."""
    return _model_name


def get_use_openrouter() -> bool:
    """Get whether OpenRouter is currently enabled."""
    return _use_openrouter


def set_model(model: str) -> None:
    """Set the model name at runtime."""
    global _model_name
    _model_name = model
    logger.info(f"GPT model changed to: {model}")


def set_use_openrouter(enabled: bool) -> None:
    """Toggle OpenRouter provider at runtime."""
    global _use_openrouter
    _use_openrouter = enabled
    logger.info(f"OpenRouter {'enabled' if enabled else 'disabled'}")


class GptQuotaExceeded(Exception):
    """Raised when the GPT API quota is exhausted and retries won't help."""
    pass


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
        
    Raises:
        GptQuotaExceeded: If the API quota is exhausted (non-retryable)
    """
    retry_count = 0
    model = _model_name
    provider = "OpenRouter" if _use_openrouter else "OpenAI"
    client = _get_client()
    
    while retry_count <= max_retries:
        try:
            logger.info(f"Sending request to {model} via {provider}")
            
            params = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "response_format": {"type": "json_object"}
            }

            if _use_openrouter:
                params["extra_headers"] = {
                    "HTTP-Referer": "https://github.com/mealiemate/mealiemate",
                    "X-Title": "MealieMate"
                }

            completion = await client.chat.completions.create(**params)
            raw_output = completion.choices[0].message.content
            
            try:
                result = json.loads(raw_output)
                logger.info("Successfully received and parsed JSON response from AI")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from AI response: {str(e)}")
                logger.debug(f"Raw response: {raw_output[:100]}...")
                return {}
                
        except asyncio.CancelledError:
            logger.warning("Request to AI was cancelled")
            raise
            
        except RateLimitError as e:
            error_body = str(e)
            if "insufficient_quota" in error_body:
                logger.error(f"API quota exhausted — not retrying: {str(e)}")
                raise GptQuotaExceeded(f"API quota exhausted: {str(e)}")
            retry_count += 1
            if retry_count <= max_retries:
                logger.warning(f"Rate limited by {provider} API: {str(e)}. Retrying ({retry_count}/{max_retries})...")
                await asyncio.sleep(retry_delay * retry_count)
            else:
                logger.error(f"Failed to get response from {provider} after {max_retries} retries: {str(e)}")
                return {}
            
        except Exception as e:
            retry_count += 1
            if retry_count <= max_retries:
                logger.warning(f"Error calling {provider} API: {str(e)}. Retrying ({retry_count}/{max_retries})...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed to get response from {provider} after {max_retries} retries: {str(e)}")
                return {}
    
    return {}
