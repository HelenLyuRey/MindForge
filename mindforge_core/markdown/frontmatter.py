from __future__ import annotations

from typing import Any


def extract_frontmatter_and_body(text: str, *, strip_body: bool = False) -> tuple[dict[str, str], str]:
    normalized = text.replace("\r\n", "\n")
    if normalized.startswith("---\n"):
        parts = normalized.split("---\n", 2)
        if len(parts) == 3:
            frontmatter_raw, body = parts[1], parts[2]
            frontmatter: dict[str, str] = {}
            for line in frontmatter_raw.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip()] = value.strip().strip('"')
            return frontmatter, body.strip() if strip_body else body
    return {}, normalized.strip() if strip_body else normalized


def yaml_escape(value: Any) -> str:
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def build_frontmatter(row: dict[str, Any], ordered_keys: list[str]) -> str:
    lines = ["---"]
    for key in ordered_keys:
        value = row.get(key, "")
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {item}" for item in value)
        else:
            lines.append(f"{key}: {yaml_escape(value)}")
    lines.append("---")
    return "\n".join(lines)
