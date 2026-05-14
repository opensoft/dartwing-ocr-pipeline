"""Host-Ollama voter over HTTP.

Single `httpx` request per invocation. No retries — that is an orchestrator
concern (spec Clarifications Q2). Maps transport errors to `OllamaUnreachable`
and server-side "model not found" to `OllamaModelUnavailable` so the CLI can
surface distinct exit codes (R-011 exits 3 and 4).
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from ..config import VoterConfig
from ..errors import OllamaModelUnavailable, OllamaUnreachable
from .base import RawModelResponse, VoterAdapter


class OllamaVoter(VoterAdapter):
    def __init__(self, *, base_url: str | None = None) -> None:
        url = base_url or os.environ.get("OLLAMA_BASE_URL", "")
        if not url:
            raise OllamaUnreachable(
                "OLLAMA_BASE_URL is not set",
                detail={"hint": "export OLLAMA_BASE_URL=http://host.docker.internal:11434"},
            )
        self._base_url = url.rstrip("/")

    def call(self, rendered_prompt: str, config: VoterConfig) -> RawModelResponse:
        url = f"{self._base_url}/api/generate"
        options: dict[str, Any] = {"temperature": config.sampling.temperature}
        if config.sampling.seed is not None:
            options["seed"] = config.sampling.seed
        if config.sampling.top_p is not None:
            options["top_p"] = config.sampling.top_p
        if config.sampling.top_k is not None:
            options["top_k"] = config.sampling.top_k
        options["num_predict"] = config.prompt.max_output_tokens

        payload: dict[str, Any] = {
            "model": config.ollama.model_tag,
            "prompt": rendered_prompt,
            "stream": False,
            "options": options,
        }
        if config.prompt.format is not None:
            payload["format"] = config.prompt.format

        timeout = httpx.Timeout(
            config.ollama.timeout_seconds,
            connect=config.ollama.connect_timeout_seconds,
        )

        started = time.monotonic()
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, json=payload)
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise OllamaUnreachable(
                f"could not connect to Ollama at {url}",
                detail={"url": url, "error": str(exc)},
            ) from exc
        except httpx.ReadTimeout as exc:
            raise OllamaUnreachable(
                f"Ollama read timed out after {config.ollama.timeout_seconds}s",
                detail={"url": url, "timeout_seconds": config.ollama.timeout_seconds},
            ) from exc
        except httpx.TransportError as exc:
            raise OllamaUnreachable(
                f"transport error calling Ollama at {url}",
                detail={"url": url, "error": str(exc)},
            ) from exc

        duration_ms = int((time.monotonic() - started) * 1000)

        if response.status_code >= 400:
            try:
                payload_err = response.json()
            except ValueError:
                payload_err = {"raw": response.text}
            message = str(payload_err.get("error", "")).lower()
            if "model" in message and ("not found" in message or "try pulling" in message):
                raise OllamaModelUnavailable(
                    f"Ollama reports model {config.ollama.model_tag!r} is unavailable",
                    detail={
                        "status_code": response.status_code,
                        "model_tag": config.ollama.model_tag,
                        "body": payload_err,
                    },
                )
            raise OllamaUnreachable(
                f"Ollama returned HTTP {response.status_code}",
                detail={"status_code": response.status_code, "body": payload_err},
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise OllamaUnreachable(
                "Ollama response was not valid JSON",
                detail={"status_code": response.status_code, "error": str(exc)},
            ) from exc

        # Ollama may return a 200 with an `error` key for soft failures.
        if isinstance(body, dict) and "error" in body:
            message = str(body["error"]).lower()
            if "model" in message and ("not found" in message or "try pulling" in message):
                raise OllamaModelUnavailable(
                    f"Ollama reports model {config.ollama.model_tag!r} is unavailable",
                    detail={"model_tag": config.ollama.model_tag, "body": body},
                )
            raise OllamaUnreachable(
                f"Ollama reported an error: {body['error']}",
                detail={"body": body},
            )

        return RawModelResponse(
            body=body.get("response", ""),
            duration_ms=duration_ms,
            model_echo=body.get("model"),
            done=bool(body.get("done", True)),
        )
