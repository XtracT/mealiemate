"""
Module: gpt_service
----------------
Provides an implementation of the GptService interface using the gpt_utils module.

This module wraps the existing gpt_utils functionality in a class that implements
the GptService interface, making it compatible with the dependency injection system.
"""

import logging
from typing import Dict, List, Any

from core.services import GptService
import utils.gpt_utils as gpt_utils

# Configure logging
logger = logging.getLogger(__name__)

class GptServiceImpl(GptService):
    """Implementation of the GptService interface using gpt_utils."""
    
    async def gpt_json_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_retries: int = 2,
        retry_delay: float = 1.0
    ) -> Dict[str, Any]:
        """
        Sends a series of messages to AI provider with JSON output and
        returns a Python dict if JSON can be parsed, or an empty dict on failure.

        Args:
            messages: A list of {"role": "...", "content": "..."} chat messages
            temperature: The temperature for the completion (0.0 to 2.0)
            max_retries: Maximum number of retry attempts on transient errors
            retry_delay: Delay between retries in seconds

        Returns:
            Parsed JSON response as dictionary or empty dict on failure
        """
        return await gpt_utils.gpt_json_chat(
            messages=messages, temperature=temperature, max_retries=max_retries, retry_delay=retry_delay
        )
