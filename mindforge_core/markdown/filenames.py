from __future__ import annotations

import re
import unicodedata


def sanitize_filename(name: str, *, max_len: int = 100, fallback: str = "Untitled") -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"[_\s]+", " ", name).strip()
    return name[:max_len].strip() or fallback


def make_filename(title: str, date: str, *, max_title_len: int = 100) -> str:
    return f"{date} {sanitize_filename(title, max_len=max_title_len)}.md"


def slugify_filename(text: str, max_len: int = 80) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r'[\\/:*?"<>|]', " ", text)
    text = re.sub(r"\s+", "-", text).strip("-._ ")
    text = text[:max_len].strip("-._ ")
    return text or "untitled"
