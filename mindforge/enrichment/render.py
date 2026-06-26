from __future__ import annotations

from typing import Any


def render_enriched_markdown(note: dict[str, Any], decision: dict[str, Any]) -> str:
    refined_title = decision["refined_title"].replace('"', '\\"')
    original_title = note["original_title"].replace('"', '\\"')
    lines = [
        "---",
        f'date: "{note["date"]}"',
        f'original_title: "{original_title}"',
        f'refined_title: "{refined_title}"',
        f'conversation_id: "{note["conversation_id"]}"',
        f'url: "{note["url"]}"',
    ]
    lines.extend(_frontmatter_list("tags", decision["tag_labels"]))
    lines.extend(_frontmatter_list("taxonomy_category_ids", decision["tag_category_ids"]))
    lines.extend(
        [
            f'classification_confidence: {decision["confidence"]}',
            "---",
            "",
            f'# {decision["refined_title"]}',
            "",
            f'_Original title: {note["original_title"]}_',
            "",
            "## Applied Taxonomy",
            "",
            f'- Tags: {", ".join(decision["tag_labels"])}',
            f'- Category IDs: {", ".join(decision["tag_category_ids"])}',
            f'- Confidence: {decision["confidence"]}',
            f'- Reason: {decision["reason"]}',
            "",
            "## Conversation",
            "",
            note["body"],
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _frontmatter_list(key: str, values: list[str]) -> list[str]:
    return [f"{key}:"] + [f"  - {value}" for value in values]
