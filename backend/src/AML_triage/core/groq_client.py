"""Groq API client with offline cassette support."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import httpx

from .config import Settings, load_settings

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


@dataclass
class PlanSuggestion:
    rationale: str
    confidence: float


class GroqClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self._client: httpx.AsyncClient | None = None

    @property
    def fixtures_dir(self) -> Path:
        return self.settings.fixtures_dir / "groq_captures"

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            timeout = httpx.Timeout(self.settings.http.timeout_seconds)
            self._client = httpx.AsyncClient(timeout=timeout)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def generate_plan_suggestion(
        self,
        *,
        prompt: str,
        schema: Dict[str, Any],
        cache_key: str,
    ) -> PlanSuggestion:
        """Return Groq-backed plan rationale or load from offline cassette."""

        if self.settings.offline_mode:
            cassette_path = self.fixtures_dir / f"{cache_key}.json"
            if cassette_path.exists():
                with cassette_path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                return PlanSuggestion(
                    rationale=payload.get("rationale", "Offline rationale unavailable"),
                    confidence=float(payload.get("confidence", 0.75)),
                )
            # Fallback deterministic rationale
            return PlanSuggestion(
                rationale="Offline mode: rationale generated from deterministic policy rules.",
                confidence=0.75,
            )

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return PlanSuggestion(
                rationale="GROQ_API_KEY missing; returning deterministic rationale.",
                confidence=0.6,
            )

        client = await self._ensure_client()
        payload = {
            "model": self.settings.llm.model_id,
            "response_format": {"type": "json_object", "schema": schema},
            "temperature": self.settings.llm.temperature,
            "messages": [
                {"role": "system", "content": "You are an AML policy planner that outputs compliant JSON."},
                {"role": "user", "content": prompt},
            ],
        }

        response = await client.post(
            GROQ_ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        obj = json.loads(content)

        rationale = obj.get("rationale", "Groq completion produced no rationale")
        confidence = float(obj.get("confidence", 0.8))

        # Store cassette for offline reuse
        cassette_path = self.fixtures_dir / f"{cache_key}.json"
        cassette_path.parent.mkdir(parents=True, exist_ok=True)
        with cassette_path.open("w", encoding="utf-8") as handle:
            json.dump({"rationale": rationale, "confidence": confidence}, handle, indent=2)

        return PlanSuggestion(rationale=rationale, confidence=confidence)

    async def generate_reviewer_report(self, *, prompt: str, cache_key: str) -> str:
        """Produce a human-readable reviewer report."""

        if self.settings.offline_mode:
            cassette_path = self.fixtures_dir / "reports" / f"{cache_key}.txt"
            if cassette_path.exists():
                return cassette_path.read_text(encoding="utf-8")
            fallback = "Offline mode: recommended actions confirmed. Follow playbook steps and monitor for customer response."
            cassette_path.parent.mkdir(parents=True, exist_ok=True)
            cassette_path.write_text(fallback, encoding="utf-8")
            return fallback

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return "GROQ_API_KEY missing; provide reviewer summary based on deterministic playbook guidance."

        client = await self._ensure_client()
        payload = {
            "model": self.settings.llm.model_id,
            "temperature": self.settings.llm.temperature,
            "messages": [
                {"role": "system", "content": "You are an AML review assistant that writes direct, compliant summaries."},
                {"role": "user", "content": prompt},
            ],
        }

        response = await client.post(
            GROQ_ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]

        cassette_path = self.fixtures_dir / "reports" / f"{cache_key}.txt"
        cassette_path.parent.mkdir(parents=True, exist_ok=True)
        cassette_path.write_text(content, encoding="utf-8")
        return content


__all__ = ["GroqClient", "PlanSuggestion"]
