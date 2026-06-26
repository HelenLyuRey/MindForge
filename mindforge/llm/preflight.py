from __future__ import annotations

from typing import Any

import requests
import urllib3

from mindforge.llm.client import LLMConfig, load_llm_config


def provider_preflight_check(
    *,
    config: LLMConfig | None = None,
    raise_on_fail: bool = True,
) -> dict[str, Any]:
    cfg = config or load_llm_config()
    result: dict[str, Any] = {"provider": cfg.provider, "ok": True, "message": ""}

    if cfg.provider == "kimi":
        _check_kimi(cfg, result)
    elif cfg.provider == "ollama":
        _check_ollama(cfg, result)
    elif cfg.provider == "openai_compatible":
        _check_openai_compatible(cfg, result)
    else:
        result["ok"] = False
        result["message"] = f"Unsupported provider: {cfg.provider}"

    if raise_on_fail and not result["ok"]:
        raise RuntimeError(str(result["message"]))
    return result


def _check_kimi(cfg: LLMConfig, result: dict[str, Any]) -> None:
    if not cfg.kimi_api_key:
        result["ok"] = False
        result["message"] = "Missing KIMI_API_KEY for Kimi provider."
        return

    try:
        url = cfg.kimi_base_url.rstrip("/") + "/models"
        verify_ssl = bool(getattr(cfg, "kimi_verify_ssl", True))
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {cfg.kimi_api_key}"},
            timeout=8,
            verify=verify_ssl,
        )
        response.raise_for_status()
        result["message"] = f"Kimi endpoint reachable at {cfg.kimi_base_url} with model {cfg.kimi_model}."
    except requests.RequestException as exc:
        result["ok"] = False
        result["message"] = f"Cannot reach Kimi endpoint at {cfg.kimi_base_url}. Error: {exc}"


def _check_ollama(cfg: LLMConfig, result: dict[str, Any]) -> None:
    try:
        response = requests.get(f"{cfg.ollama_base_url}/api/tags", timeout=8)
        response.raise_for_status()
        models = [item.get("name", "") for item in response.json().get("models", [])]
        has_model = any(
            name == cfg.ollama_model or name.startswith(f"{cfg.ollama_model}:") for name in models
        )
        if has_model:
            result["message"] = f"Ollama ready at {cfg.ollama_base_url} with model {cfg.ollama_model}."
        else:
            result["ok"] = False
            result["message"] = f"Model not found: {cfg.ollama_model}. Available: {models[:8]}"
    except requests.RequestException as exc:
        result["ok"] = False
        result["message"] = f"Cannot reach Ollama at {cfg.ollama_base_url}. Error: {exc}"


def _check_openai_compatible(cfg: LLMConfig, result: dict[str, Any]) -> None:
    missing = [
        name
        for name, value in {
            "OPENAI_BASE_URL": cfg.openai_base_url,
            "OPENAI_API_KEY": cfg.openai_api_key,
            "OPENAI_MODEL": cfg.openai_model,
        }.items()
        if not value
    ]
    if missing:
        result["ok"] = False
        result["message"] = f"Missing required settings for openai_compatible: {missing}"
        return

    try:
        url = cfg.openai_base_url.rstrip("/") + "/models"
        response = requests.get(url, headers={"Authorization": f"Bearer {cfg.openai_api_key}"}, timeout=8)
        response.raise_for_status()
        result["message"] = f"OpenAI-compatible endpoint reachable: {cfg.openai_base_url}"
    except requests.RequestException as exc:
        result["ok"] = False
        result["message"] = f"Cannot reach openai_compatible endpoint at {cfg.openai_base_url}. Error: {exc}"
