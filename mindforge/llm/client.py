from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

from mindforge.config import load_project_env
from mindforge.llm.json_utils import parse_json_robust
from mindforge.llm.kimi import kimi_call_json


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "kimi"
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_api_key: str = ""
    kimi_model: str = "kimi-k2.6"
    kimi_verify_ssl: bool = True
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    openai_base_url: str = ""
    openai_api_key: str = ""
    openai_model: str = ""
    retries: int = 2
    request_timeout_sec: int = 300


def load_llm_config(
    *,
    provider: str | None = None,
    retries: int | None = None,
    request_timeout_sec: int | None = None,
) -> LLMConfig:
    load_project_env()
    # Kimi is the paid default provider now. Set LLM_PROVIDER=ollama to switch
    # back to the local free Ollama path without changing code.
    provider_name = provider or os.getenv("LLM_PROVIDER") or os.getenv("TAXONOMY_PROVIDER", "kimi")
    return LLMConfig(
        provider=provider_name,
        kimi_base_url=os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1"),
        kimi_api_key=os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY", ""),
        kimi_model=os.getenv("KIMI_MODEL", "kimi-k2.6"),
        kimi_verify_ssl=_env_bool("KIMI_VERIFY_SSL", default=True),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct"),
        openai_base_url=os.getenv("OPENAI_BASE_URL", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", ""),
        retries=retries if retries is not None else int(os.getenv("PIPELINE_RETRIES", "2")),
        request_timeout_sec=(
            request_timeout_sec
            if request_timeout_sec is not None
            else int(os.getenv("PIPELINE_REQUEST_TIMEOUT_SEC", "300"))
        ),
    )


def llm_call_json(
    system_prompt: str,
    user_prompt: str,
    *,
    config: LLMConfig | None = None,
    temperature: float = 0.0,
) -> dict[str, Any]:
    cfg = config or load_llm_config()

    if cfg.provider == "kimi":
        return kimi_call_json(cfg, system_prompt, user_prompt, temperature)

    # Ollama support is intentionally kept for switching back to the local free
    # model. Use LLM_PROVIDER=ollama with OLLAMA_* settings when needed.
    if cfg.provider == "ollama":
        return _ollama_call_json(cfg, system_prompt, user_prompt, temperature)

    if cfg.provider == "openai_compatible":
        return _openai_compatible_call_json(cfg, system_prompt, user_prompt, temperature)

    raise ValueError(f"Unsupported provider: {cfg.provider}")


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _ollama_call_json(
    cfg: LLMConfig,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
) -> dict[str, Any]:
    payload = {
        "model": cfg.ollama_model,
        "prompt": f"<|system|>\n{system_prompt}\n<|user|>\n{user_prompt}\n<|assistant|>",
        "stream": False,
        "options": {"temperature": temperature},
        "format": "json",
    }

    last_error: Exception | None = None
    for attempt in range(cfg.retries + 1):
        try:
            response = requests.post(
                f"{cfg.ollama_base_url}/api/generate",
                json=payload,
                timeout=cfg.request_timeout_sec,
            )
            response.raise_for_status()
            return parse_json_robust(response.json().get("response", "{}"))
        except (requests.RequestException, RuntimeError) as exc:
            last_error = exc
            if attempt >= cfg.retries:
                break

    raise RuntimeError(f"Ollama call failed after retries: {last_error}")


def _openai_compatible_call_json(
    cfg: LLMConfig,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
) -> dict[str, Any]:
    if not cfg.openai_base_url or not cfg.openai_api_key or not cfg.openai_model:
        raise ValueError("Set OPENAI_BASE_URL, OPENAI_API_KEY, and OPENAI_MODEL first")

    url = cfg.openai_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg.openai_model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=cfg.request_timeout_sec)
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        return parse_json_robust(text)
    except requests.RequestException as exc:
        raise RuntimeError(
            f"openai_compatible request failed at {url} with model {cfg.openai_model}: {exc}"
        ) from exc
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("openai_compatible returned an unexpected response shape") from exc
