from __future__ import annotations

from typing import Any

import requests
import urllib3

from mindforge.llm.json_utils import parse_json_robust


def kimi_call_json(
    cfg: Any,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
) -> dict[str, Any]:
    """Call Kimi through Moonshot's OpenAI-compatible chat completions API."""
    if not cfg.kimi_api_key:
        raise ValueError("Set KIMI_API_KEY in .env before using LLM_PROVIDER=kimi")

    url = cfg.kimi_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": cfg.kimi_model,
        "response_format": {"type": "json_object"},
        # Mirrors the official Kimi sample:
        # extra_body={"thinking": {"type": "disabled"}}
        "thinking": {"type": "disabled"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    # Kimi K2.6 uses fixed sampling values in non-thinking mode and rejects
    # arbitrary temperature values, so we intentionally omit temperature for it.
    if not str(cfg.kimi_model).startswith("kimi-k2."):
        payload["temperature"] = temperature
    headers = {
        "Authorization": f"Bearer {cfg.kimi_api_key}",
        "Content-Type": "application/json",
    }
    verify_ssl = bool(getattr(cfg, "kimi_verify_ssl", True))
    if not verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    last_error: Exception | None = None
    for attempt in range(cfg.retries + 1):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=cfg.request_timeout_sec,
                verify=verify_ssl,
            )
            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                raise RuntimeError(f"{exc}; response={response.text[:500]}") from exc
            text = response.json()["choices"][0]["message"]["content"]
            return parse_json_robust(text)
        except (requests.RequestException, KeyError, IndexError, TypeError, RuntimeError) as exc:
            last_error = exc
            if attempt >= cfg.retries:
                break

    raise RuntimeError(f"Kimi call failed after retries at {url} with model {cfg.kimi_model}: {last_error}")
