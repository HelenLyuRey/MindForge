from __future__ import annotations

from typing import Any


def extract_frontmatter_and_body(text: str, *, strip_body: bool = False) -> tuple[dict[str, Any], str]:
    normalized = text.replace("\r\n", "\n")
    if normalized.startswith("---\n"):
        parts = normalized.split("---\n", 2)
        if len(parts) == 3:
            frontmatter_raw, body = parts[1], parts[2]
            return _parse_frontmatter(frontmatter_raw), body.strip() if strip_body else body
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


def _parse_frontmatter(frontmatter_raw: str) -> dict[str, Any]:
    frontmatter: dict[str, Any] = {}
    current_list_key: str | None = None

    for raw_line in frontmatter_raw.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            current_list_key = None
            continue

        list_item = _parse_list_item(line)
        if list_item is not None and current_list_key is not None:
            items = frontmatter.get(current_list_key)
            if not isinstance(items, list):
                items = []
                frontmatter[current_list_key] = items
            items.append(list_item)
            continue

        if ":" in line and not line.lstrip().startswith("- "):
            key, raw_value = line.split(":", 1)
            key = key.strip()
            raw_value = raw_value.strip()
            if raw_value == "":
                frontmatter[key] = []
                current_list_key = key
            elif raw_value in {'""', "''"}:
                frontmatter[key] = ""
                current_list_key = None
            else:
                frontmatter[key] = raw_value.strip('"')
                current_list_key = None
            continue

        current_list_key = None

    return frontmatter


def _parse_list_item(line: str) -> str | None:
    stripped = line.strip()
    if stripped.startswith("- "):
        return stripped[2:].strip().strip('"')
    return None
