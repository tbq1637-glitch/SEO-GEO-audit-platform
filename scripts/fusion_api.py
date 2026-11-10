"""Bounded, diagnostics-first OpenAI STEP 5 request.

No background retries. Preserve source artifact, log request scope without
sensitive content, and retry only transient API/connection/time-out failures.
"""
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError


def summarize_input(evidence, serialized):
    return {
        "input_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "input_characters": len(serialized),
        "rough_tokens_at_four_chars_per_token": len(serialized) // 4,
        "estimate_is_not_billed_token_usage": True,
        "top_level_evidence_sources": [
            {"name": key, "serialized_characters": len(json.dumps(value, ensure_ascii=False))}
            for key, value in sorted(
                evidence.items(), key=lambda kv: -len(json.dumps(kv[1], ensure_ascii=False))
            )
        ],
    }


def call_fusion(client, model, system_prompt, serialized, evidence,
                diagnostics_file, timeout_seconds=300, max_attempts=2, sleep_fn=time.sleep):
    diagnostics_file = Path(diagnostics_file)
    diagnostics_file.parent.mkdir(parents=True, exist_ok=True)
    max_attempts = min(2, max(1, int(max_attempts)))
    timeout_seconds = min(420, max(90, int(timeout_seconds)))
    info = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": model,
        "request_timeout_seconds": timeout_seconds,
        "attempt_limit": max_attempts,
        "request_input": summarize_input(evidence, serialized),
        "attempts": [],
        "outcome": "pending",
        "no_raw_page_text_or_api_keys_logged": True,
    }

    def save():
        diagnostics_file.write_text(
            json.dumps(info, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")

    save()
    for index in range(1, max_attempts + 1):
        attempt = {"number": index}
        started = time.monotonic()
        try:
            response = client.responses.create(
                model=model,
                reasoning={"effort": "high"},
                input=[{"role": "system", "content": system_prompt},
                       {"role": "user", "content": serialized}],
                timeout=timeout_seconds,
            )
            attempt["duration_seconds"] = round(time.monotonic() - started, 2)
            attempt["api_status"] = getattr(response, "status", None)
            details = getattr(response, "incomplete_details", None)
            attempt["incomplete_reason"] = getattr(details, "reason", None)
            usage = getattr(response, "usage", None)
            if usage is not None:
                attempt["usage"] = {
                    "input_tokens": getattr(usage, "input_tokens", None),
                    "output_tokens": getattr(usage, "output_tokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None),
                }
            info["attempts"].append(attempt)
            report = str(getattr(response, "output_text", "") or "").strip()
            if (attempt["api_status"] != "completed"
                    or details is not None or not report):
                info["outcome"] = "incomplete"
                save()
                raise RuntimeError("STEP 5 API output was incomplete or empty; not published")
            info["outcome"] = "completed"
            save()
            return report
        except (APITimeoutError, APIConnectionError, InternalServerError,
                RateLimitError) as exc:
            attempt["duration_seconds"] = round(time.monotonic() - started, 2)
            attempt["failure_type"] = type(exc).__name__
            attempt["http_status"] = getattr(exc, "status_code", None)
            attempt["transient"] = True
            info["attempts"].append(attempt)
            info["outcome"] = "retrying" if index < max_attempts else "failed"
            save()
            if index >= max_attempts:
                raise
            sleep_fn(8)
        except Exception as exc:
            if attempt not in info["attempts"]:
                attempt["duration_seconds"] = round(time.monotonic() - started, 2)
                attempt["failure_type"] = type(exc).__name__
                attempt["transient"] = False
                info["attempts"].append(attempt)
                info["outcome"] = "failed"
                save()
            raise
    raise RuntimeError("No completed STEP 5 response")
