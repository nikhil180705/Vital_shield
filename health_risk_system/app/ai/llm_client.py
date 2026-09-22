"""
llm_client.py — OpenAI-compatible LM Studio client.

Configured against the locally hosted LM Studio instance.
Does NOT use any cloud LLM API.

Gracefully handles:
  - LM Studio not running
  - Connection timeouts
  - Malformed JSON responses
  - Empty responses
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from openai import OpenAI, APIConnectionError, APITimeoutError, APIStatusError

from app.config import (
    LM_STUDIO_API_KEY,
    LM_STUDIO_BASE_URL,
    LM_STUDIO_MAX_TOKENS,
    LM_STUDIO_MODEL,
    LM_STUDIO_TEMPERATURE,
    LM_STUDIO_TIMEOUT,
)

# Short timeout for the availability check probe — avoids long waits when LM Studio is down
_AVAILABILITY_PROBE_TIMEOUT: int = 5

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Thin wrapper around the OpenAI-compatible LM Studio endpoint.

    Usage:
        client = LLMClient()
        result = client.chat(system_prompt, user_prompt)
        if result["success"]:
            data = result["json_data"]
    """

    def __init__(self) -> None:
        self._client = OpenAI(
            base_url=LM_STUDIO_BASE_URL,
            api_key=LM_STUDIO_API_KEY,
            timeout=LM_STUDIO_TIMEOUT,
        )
        self.model = LM_STUDIO_MODEL
        self._available: Optional[bool] = None  # Cached availability

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def is_available(self, force_check: bool = False) -> bool:
        """Check if LM Studio is reachable (cached after first check)."""
        if self._available is not None and not force_check:
            return self._available

        # Fast TCP socket probe — avoids httpx connection retry delays
        import socket
        import urllib.parse

        parsed = urllib.parse.urlparse(LM_STUDIO_BASE_URL)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 1234

        try:
            with socket.create_connection((host, port), timeout=2.0):
                pass
            self._available = True
            logger.info("LM Studio is available at %s", LM_STUDIO_BASE_URL)
        except (OSError, ConnectionRefusedError, socket.timeout):
            self._available = False
            logger.warning(
                "LM Studio is NOT available at %s. AI analysis will be skipped.",
                LM_STUDIO_BASE_URL,
            )
        return self._available

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        expect_json: bool = True,
    ) -> Dict[str, Any]:
        """
        Send a chat request to LM Studio.

        Returns a dict:
        {
            "success": bool,
            "raw_text": str | None,
            "json_data": dict | None,
            "error": str | None,
            "unavailable": bool,
        }
        """
        if not self.is_available():
            return {
                "success": False,
                "raw_text": None,
                "json_data": None,
                "error": "LM Studio is unavailable.",
                "unavailable": True,
            }

        try:
            logger.info("Sending request to LM Studio model=%s", self.model)
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=LM_STUDIO_TEMPERATURE,
                max_tokens=LM_STUDIO_MAX_TOKENS,
            )

            raw_text = response.choices[0].message.content or ""
            logger.debug("Raw LLM response: %s", raw_text[:500])

            if not expect_json:
                return {
                    "success": True,
                    "raw_text": raw_text,
                    "json_data": None,
                    "error": None,
                    "unavailable": False,
                }

            # ----------------------------------------------------------------
            # JSON extraction with multiple fallback strategies
            # ----------------------------------------------------------------
            json_data = self._extract_json(raw_text)
            if json_data is not None:
                return {
                    "success": True,
                    "raw_text": raw_text,
                    "json_data": json_data,
                    "error": None,
                    "unavailable": False,
                }
            else:
                logger.warning("Could not extract valid JSON from LLM response.")
                return {
                    "success": False,
                    "raw_text": raw_text,
                    "json_data": None,
                    "error": "Could not parse JSON from LLM response.",
                    "unavailable": False,
                }

        except APIConnectionError as e:
            self._available = False  # Reset cache on connection failure (port closed)
            logger.error("LM Studio connection failed: %s", e)
            return {
                "success": False,
                "raw_text": None,
                "json_data": None,
                "error": f"LM Studio connection failed: {e}",
                "unavailable": True,
            }
        except APITimeoutError as e:
            # Timeout means server is running, but inference is slow.
            # Do NOT mark LM Studio as unavailable!
            logger.warning("LM Studio request timed out: %s", e)
            return {
                "success": False,
                "raw_text": None,
                "json_data": None,
                "error": f"LM Studio request timed out: {e}",
                "unavailable": False,
            }
        except APIStatusError as e:
            logger.error("LM Studio API error: %s", e)
            return {
                "success": False,
                "raw_text": None,
                "json_data": None,
                "error": f"LM Studio API error: {e}",
                "unavailable": False,
            }
        except Exception as e:
            logger.error("Unexpected error calling LLM: %s", e, exc_info=True)
            return {
                "success": False,
                "raw_text": None,
                "json_data": None,
                "error": f"Unexpected error: {e}",
                "unavailable": False,
            }

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _try_parse_json(self, snippet: str) -> Optional[Dict]:
        """Try parsing JSON, with recovery for trailing commas."""
        snippet = snippet.strip()
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            pass
        # Clean trailing commas: ,} -> } and ,] -> ]
        cleaned = re.sub(r",\s*([\}\]])", r"\1", snippet)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None

    def _extract_json(self, text: str) -> Optional[Dict]:
        """
        Attempt to extract a JSON object from the model's response.

        Strategies:
        1. Direct JSON parse of the whole response.
        2. Extract from markdown code blocks (```json ... ``` or ``` ... ```).
        3. Find the outermost { … } block.
        """
        # Strip Qwen thinking tags if present
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # Strategy 1: Direct parse
        parsed = self._try_parse_json(text)
        if parsed is not None:
            return parsed

        # Strategy 2: Markdown code blocks
        code_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        for block in code_blocks:
            parsed = self._try_parse_json(block)
            if parsed is not None:
                return parsed

        # Strategy 3: First / outermost { ... } block
        brace_block = re.search(r"(\{.*\})", text, re.DOTALL)
        if brace_block:
            parsed = self._try_parse_json(brace_block.group(1))
            if parsed is not None:
                return parsed

        return None
