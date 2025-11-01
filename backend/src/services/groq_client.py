"""
Groq API client for Kimi K2 model integration.
Feature: 003-langgraph-rule-extraction
"""

import asyncio
import json
from typing import Any
import structlog
from groq import AsyncGroq
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class GroqRateLimitError(Exception):
    """Raised when Groq API rate limit is hit."""
    pass


class GroqClient:
    """
    Async Groq client for Kimi K2 model with retry logic and cost tracking.

    Features:
    - Automatic retry with exponential backoff
    - Token usage and cost calculation
    - JSON mode for structured outputs
    - Chain-of-thought prompting support
    """

    MODEL = "moonshotai/kimi-k2-instruct-0905"
    MAX_TOKENS = 128000  # Kimi K2 context window
    DEFAULT_TEMPERATURE = 0.1  # Low temperature for factual extraction

    def __init__(self, api_key: str | None = None):
        self.client = AsyncGroq(api_key=api_key or settings.GROQ_API_KEY)
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(GroqRateLimitError),
        reraise=True
    )
    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """
        Send chat completion request to Kimi K2.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (default: 0.1 for factual)
            max_tokens: Max output tokens
            response_format: Optional {"type": "json_object"} for JSON mode

        Returns:
            Tuple of (response_text, metadata_dict)
            metadata_dict contains: tokens_used, latency_ms, finish_reason

        Raises:
            GroqRateLimitError: On rate limit (triggers retry)
            Exception: On other API errors
        """
        import time

        start_time = time.time()

        try:
            completion = await self.client.chat.completions.create(
                model=self.MODEL,
                messages=messages,
                temperature=temperature or self.DEFAULT_TEMPERATURE,
                max_tokens=max_tokens,
                response_format=response_format,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Extract response
            response_text = completion.choices[0].message.content or ""
            finish_reason = completion.choices[0].finish_reason

            # Track token usage
            usage = completion.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0

            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens

            metadata = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "latency_ms": latency_ms,
                "finish_reason": finish_reason,
                "model": self.MODEL,
            }

            logger.info(
                "Groq completion successful",
                tokens=metadata["total_tokens"],
                latency_ms=latency_ms,
                finish_reason=finish_reason
            )

            return response_text, metadata

        except Exception as e:
            error_msg = str(e)

            # Check for rate limit errors
            if "rate_limit" in error_msg.lower() or "429" in error_msg:
                logger.warning("Groq rate limit hit, retrying...")
                raise GroqRateLimitError(error_msg)

            logger.error("Groq API error", error=error_msg)
            raise

    async def extract_structured_data(
        self,
        system_prompt: str,
        user_content: str,
        json_schema: dict | None = None,
        temperature: float = 0.1,
    ) -> tuple[dict, dict]:
        """
        Extract structured JSON data using JSON mode.

        Args:
            system_prompt: System instructions for extraction task
            user_content: Document text or context to extract from
            json_schema: Optional JSON schema for output validation
            temperature: Sampling temperature

        Returns:
            Tuple of (parsed_json_dict, metadata_dict)

        Raises:
            json.JSONDecodeError: If response is not valid JSON
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        # Enable JSON mode
        response_format = {"type": "json_object"}

        response_text, metadata = await self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=4096,
            response_format=response_format,
        )

        try:
            parsed_json = json.loads(response_text)

            # Optional schema validation
            if json_schema:
                # TODO: Add jsonschema validation if needed
                pass

            return parsed_json, metadata

        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response", error=str(e), response=response_text[:500])
            # Return empty result with error metadata
            return {
                "error": "Invalid JSON response",
                "raw_response": response_text[:1000]
            }, {**metadata, "parse_error": str(e)}

    async def extract_with_cot(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.2,
    ) -> tuple[dict, dict]:
        """
        Extract structured data with chain-of-thought reasoning.

        Asks model to explain reasoning before providing JSON output.

        Args:
            system_prompt: System instructions
            user_content: Content to analyze
            temperature: Slightly higher for reasoning

        Returns:
            Tuple of (parsed_json_with_reasoning, metadata_dict)
        """
        cot_prompt = f"""
{system_prompt}

IMPORTANT: First explain your reasoning step-by-step, then provide the final JSON output.

Format your response as:

REASONING:
<your step-by-step analysis>

OUTPUT:
<valid JSON object>
"""

        messages = [
            {"role": "system", "content": cot_prompt},
            {"role": "user", "content": user_content}
        ]

        response_text, metadata = await self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=6000,
        )

        # Parse reasoning and JSON output
        try:
            parts = response_text.split("OUTPUT:", 1)
            reasoning = parts[0].replace("REASONING:", "").strip() if len(parts) > 1 else ""
            json_part = parts[1].strip() if len(parts) > 1 else response_text

            # Extract JSON from code block if present
            if "```json" in json_part:
                json_part = json_part.split("```json")[1].split("```")[0].strip()
            elif "```" in json_part:
                json_part = json_part.split("```")[1].split("```")[0].strip()

            parsed_json = json.loads(json_part)
            parsed_json["_reasoning"] = reasoning  # Attach reasoning to result

            return parsed_json, metadata

        except (json.JSONDecodeError, IndexError) as e:
            logger.error("Failed to parse CoT response", error=str(e))
            return {
                "error": "Invalid CoT response",
                "raw_response": response_text[:1000]
            }, {**metadata, "parse_error": str(e)}

    def get_total_cost(self) -> float:
        """
        Calculate total cost of all API calls made by this client instance.

        Returns:
            Total cost in USD
        """
        from workflows.schemas.rule_schemas import calculate_extraction_cost
        return calculate_extraction_cost(self.total_input_tokens, self.total_output_tokens)

    def reset_metrics(self):
        """Reset token counters."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0


# Factory function
def create_groq_client() -> GroqClient:
    """Create GroqClient instance with API key from settings."""
    return GroqClient()
