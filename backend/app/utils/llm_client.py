"""
LLM Client Wrapper
Unified OpenAI-compatible API calls
"""

import json
import re
import time
import logging
from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..config import Config

logger = logging.getLogger('mirofish.llm_client')

# Transient errors worth retrying (network blips, rate limits, provider 5xx).
# Imported defensively so an older/newer openai SDK can't break import.
try:
    from openai import (
        APITimeoutError,
        RateLimitError,
        APIConnectionError,
        InternalServerError,
    )
    _TRANSIENT_ERRORS = (
        APITimeoutError,
        RateLimitError,
        APIConnectionError,
        InternalServerError,
    )
except ImportError:  # pragma: no cover - depends on SDK version
    _TRANSIENT_ERRORS = ()


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

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.REQUEST_TIMEOUT,
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
            Model response text
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            kwargs["response_format"] = response_format

        # Retry transient failures with exponential backoff so a single network
        # blip or provider 5xx doesn't abort a long pipeline (e.g. discarding a
        # report that already has completed sections).
        response = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(**kwargs)
                break
            except _TRANSIENT_ERRORS as e:
                if attempt == self.MAX_RETRIES - 1:
                    raise
                delay = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(
                    f"LLM call failed ({type(e).__name__}); retry "
                    f"{attempt + 1}/{self.MAX_RETRIES - 1} in {delay}s"
                )
                time.sleep(delay)

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
