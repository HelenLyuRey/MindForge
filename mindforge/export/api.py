from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import markdownify
import requests


DEEPSEEK_BASE_URL = "https://chat.deepseek.com"
DEEPSEEK_API_BASE = "https://chat.deepseek.com/api/v0"
logger = logging.getLogger(__name__)


def api_request(
    session: requests.Session,
    endpoint: str,
    *,
    method: str = "GET",
    max_retries: int = 3,
    retry_delay_sec: float = 2.0,
    **kwargs: Any,
) -> dict[str, Any]:
    url = f"{DEEPSEEK_API_BASE}/{endpoint.lstrip('/')}"
    for attempt in range(1, max_retries + 1):
        try:
            response = session.request(method, url, timeout=30, **kwargs)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 401:
                raise PermissionError("DeepSeek auth token expired")
        except (requests.ConnectionError, requests.Timeout):
            pass

        if attempt < max_retries:
            time.sleep(retry_delay_sec)

    raise RuntimeError(f"API {endpoint} failed after {max_retries} attempts")


def fetch_conversations_api(
    session: requests.Session,
    *,
    request_delay_sec: float = 1.0,
) -> list[dict[str, Any]] | None:
    conversations: list[dict[str, Any]] = []
    last_seq_id = None

    while True:
        endpoint = "chat_session/fetch_page"
        if last_seq_id is not None:
            endpoint += f"?before_seq_id={last_seq_id}"

        data = api_request(session, endpoint)
        biz_data = data.get("data", {}).get("biz_data", {})
        sessions = biz_data.get("chat_sessions", [])
        has_more = biz_data.get("has_more", False)
        if not sessions:
            break

        for item in sessions:
            conversation_id = str(item.get("id", ""))
            seq_id = item.get("seq_id")
            if seq_id is not None and (last_seq_id is None or seq_id < last_seq_id):
                last_seq_id = seq_id

            raw_updated_at = item.get("updated_at") or item.get("created_at")
            conversations.append(
                {
                    "conversation_id": conversation_id,
                    "original_title": item.get("title") or "Untitled",
                    "date": _parse_deepseek_date(raw_updated_at),
                    "updated_at": _normalize_deepseek_timestamp(raw_updated_at),
                    "url": f"{DEEPSEEK_BASE_URL}/a/{conversation_id}",
                }
            )

        if not has_more:
            break
        time.sleep(request_delay_sec)

    return conversations or None


def fetch_conversations_fallback(
    *,
    scripts_dir: Path,
    cookie_file: Path,
    page_load_timeout_ms: int = 30_000,
) -> list[dict[str, Any]]:
    script_path = scripts_dir / "pw_fetch_convos.py"
    result = subprocess.run(
        [sys.executable, str(script_path), str(cookie_file), str(page_load_timeout_ms)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Fallback scraping failed:\n{result.stderr[-500:]}")

    for line in result.stdout.splitlines():
        if line.startswith("RESULT:"):
            conversations = json.loads(line[7:])
            for conversation in conversations:
                conversation.setdefault("date", "unknown-date")
            return conversations

    raise RuntimeError("No result from fallback conversation scraping")


def fetch_all_conversations(
    session: requests.Session,
    *,
    scripts_dir: Path,
    cookie_file: Path,
    request_delay_sec: float = 1.0,
    page_load_timeout_ms: int = 30_000,
) -> list[dict[str, Any]]:
    try:
        conversations = fetch_conversations_api(session, request_delay_sec=request_delay_sec)
        if conversations:
            logger.info("Fetched %s conversations from DeepSeek API with update timestamps.", len(conversations))
            return conversations
    except PermissionError:
        raise
    except Exception as exc:
        logger.info("DeepSeek API conversation fetch failed; falling back to Playwright: %s", exc)

    logger.info("Fetching conversations with Playwright fallback; update timestamps are unavailable.")
    return fetch_conversations_fallback(
        scripts_dir=scripts_dir,
        cookie_file=cookie_file,
        page_load_timeout_ms=page_load_timeout_ms,
    )


def fetch_messages_api(session: requests.Session, conversation_id: str) -> list[dict[str, str]] | None:
    data = api_request(session, f"chat/history_messages?chat_session_id={conversation_id}")
    raw_messages = data.get("data", {}).get("biz_data", {}).get("chat_messages", [])
    if not raw_messages:
        return None

    messages: list[dict[str, str]] = []
    for message in raw_messages:
        role = str(message.get("role", "")).lower()
        if role not in ("user", "assistant"):
            continue

        content = str(message.get("content", "")).strip()
        if role == "assistant":
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            content = re.sub(r"<reasoning>.*?</reasoning>", "", content, flags=re.DOTALL).strip()

        if content:
            messages.append({"role": role, "content": content})

    return messages or None


def fetch_messages_fallback(
    conversation_id: str,
    conversation_url: str,
    *,
    scripts_dir: Path,
    cookie_file: Path,
    page_load_timeout_ms: int = 30_000,
) -> list[dict[str, str]]:
    script_path = scripts_dir / "pw_fetch_messages.py"
    result = subprocess.run(
        [sys.executable, str(script_path), str(cookie_file), conversation_url, str(page_load_timeout_ms)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"DOM scraping failed for {conversation_id[:8]}: {result.stderr[-300:]}")

    for line in result.stdout.splitlines():
        if line.startswith("RESULT:"):
            raw_messages = json.loads(line[7:])
            messages: list[dict[str, str]] = []
            for message in raw_messages:
                html = message.get("html", "")
                content = (
                    markdownify.markdownify(html, heading_style="ATX", strip=["img"])
                    if html
                    else message.get("content", "")
                )
                if str(content).strip():
                    messages.append({"role": message["role"], "content": str(content).strip()})
            return messages

    raise RuntimeError(f"No result from DOM scraping for {conversation_id[:8]}")


def fetch_messages(
    session: requests.Session,
    conversation_id: str,
    conversation_url: str,
    *,
    scripts_dir: Path,
    cookie_file: Path,
    page_load_timeout_ms: int = 30_000,
) -> list[dict[str, str]]:
    try:
        messages = fetch_messages_api(session, conversation_id)
        if messages:
            return messages
    except PermissionError:
        raise
    except Exception:
        pass

    return fetch_messages_fallback(
        conversation_id,
        conversation_url,
        scripts_dir=scripts_dir,
        cookie_file=cookie_file,
        page_load_timeout_ms=page_load_timeout_ms,
    )


def _parse_deepseek_date(raw_date: Any) -> str:
    if isinstance(raw_date, (int, float)):
        return _datetime_from_deepseek_timestamp(raw_date).strftime("%Y-%m-%d")
    if isinstance(raw_date, str) and raw_date:
        try:
            return datetime.fromisoformat(raw_date.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except ValueError:
            return raw_date[:10] if len(raw_date) >= 10 else "unknown-date"
    return "unknown-date"


def _normalize_deepseek_timestamp(raw_date: Any) -> str:
    if isinstance(raw_date, (int, float)):
        return _datetime_from_deepseek_timestamp(raw_date).isoformat().replace("+00:00", "Z")
    if isinstance(raw_date, str) and raw_date:
        try:
            parsed = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            return raw_date
    return ""


def _datetime_from_deepseek_timestamp(raw_date: int | float) -> datetime:
    timestamp = raw_date / 1000 if raw_date > 10_000_000_000 else raw_date
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)
