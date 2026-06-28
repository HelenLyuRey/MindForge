from __future__ import annotations

import re


def detect_language_simple(text: str) -> str:
    zh_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    en_chars = len(re.findall(r"[A-Za-z]", text))
    total = zh_chars + en_chars
    if total == 0:
        return "unknown"

    zh_ratio = zh_chars / total
    if zh_ratio > 0.65:
        return "zh"
    if zh_ratio < 0.35:
        return "en"
    return "mixed"
