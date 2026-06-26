from __future__ import annotations

import os

import requests

from mindforge.config import load_project_env


def load_deepseek_token() -> str:
    load_project_env()
    token = os.getenv("DEEPSEEK_TOKEN", "").strip()
    if not token or token == "paste_your_token_here":
        raise ValueError(
            "DEEPSEEK_TOKEN is not set. Add it to .env before running the export stage."
        )
    return token


def build_authenticated_session(token: str | None = None) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token or load_deepseek_token()}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "x-client-platform": "web",
            "x-client-locale": "en_US",
        }
    )
    return session
