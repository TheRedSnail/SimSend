"""
LLM Client Wrapper
Unified OpenAI-compatible API calls
"""

import json
import re
import logging
from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..config import Config
from .retry import call_with_retry, is_transient_error

logger = logging.getLogger('mirofish.llm_client')


class LLMClient:
    """LLM Client"""

    # Retry policy for transient API failures.
    MAX_RETRIES = 3
    REQUEST_TIMEOUT = 120.0  # seconds; a hung provider must not stall pipelines

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY is not configured")

        # max_retries=0: chat() owns the retry policy. Leaving the SDK's own two
        # retries on as well would turn 3 attempts into 9.
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.REQUEST_TIMEOUT,
            max_retries=0,
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Send a chat request

        Args:
            messages: List of messages
            temperature: Temperature parameter
            max_tokens: Maximum number of tokens
            response_format: Response format (e.g., JSON mode)

        Returns:
            Model response text. May be '' (content filter, tool-only or empty
            completion); callers that need content must treat '' as a failure.
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            kwargs["response_format"] = response_format

        # Retry transient failures (timeouts, 429, 5xx) with exponential backoff
        # so a single network blip doesn't abort a long pipeline. Permanent
        # errors (bad request, auth) are raised immediately.
        response = call_with_retry(
            self.client.chat.completions.create,
            max_retries=self.MAX_RETRIES - 1,
            initial_delay=1.0,
            retry_if=is_transient_error,
            description="LLM call",
            **kwargs,
        )

        content = response.choices[0].message.content
        # Content can be None (content filter, tool-only choice, empty
        # completion). Treat as empty rather than crashing in re.sub.
        if content is None:
            return ''
        # Some models (e.g., MiniMax M2.5) include <think> content in the response; remove it
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        return content

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Send a chat request and return JSON

        Args:
            messages: List of messages
            temperature: Temperature parameter
            max_tokens: Maximum number of tokens

        Returns:
            Parsed JSON object
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        # Clean markdown code block markers
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON format returned by LLM: {cleaned_response}")
