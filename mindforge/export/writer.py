from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mindforge.markdown.filenames import make_filename


def generate_markdown(conversation: dict[str, Any], messages: list[dict[str, str]]) -> str:
    title = conversation.get("original_title", "Untitled")
    date = conversation.get("date", "unknown-date")
    conversation_id = conversation.get("conversation_id", "")
    url = conversation.get("url", "")
    safe_title = str(title).replace('"', '\\"')

    lines = [
        "---",
        f'date: "{date}"',
        f'original_title: "{safe_title}"',
        f'conversation_id: "{conversation_id}"',
        f'url: "{url}"',
        "---",
        "",
        f"# {title}",
        "",
    ]

    for message in messages:
        lines.append(f"**{message['role']}**: {message['content']}")
        lines.append("")

    return "\n".join(lines)


def write_exported_conversation(
    export_dir: Path,
    conversation: dict[str, Any],
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    export_dir.mkdir(parents=True, exist_ok=True)
    filename = make_filename(
        str(conversation.get("original_title", "Untitled")),
        str(conversation.get("date", "unknown-date")),
        max_title_len=80,
    )
    path = export_dir / filename
    path.write_text(generate_markdown(conversation, messages), encoding="utf-8")
    return {
        "conversation_id": conversation["conversation_id"],
        "original_title": conversation.get("original_title", "Untitled"),
        "date": conversation.get("date", "unknown-date"),
        "url": conversation.get("url", ""),
        "file_name": filename,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }
