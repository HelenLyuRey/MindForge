from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mindforge.config import ProjectPaths, get_paths
from mindforge.export.api import fetch_all_conversations, fetch_messages
from mindforge.export.auth import build_authenticated_session
from mindforge.export.writer import write_exported_conversation
from mindforge.manifests import load_json_manifest, save_json_manifest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExportConfig:
    paths: ProjectPaths = get_paths()
    request_delay_sec: float = 1.0
    page_load_timeout_ms: int = 30_000

    @property
    def manifest_file(self) -> Path:
        return self.paths.export_dir / "conversations_manifest.json"

    @property
    def failure_log(self) -> Path:
        return self.paths.export_dir / "failed_exports.log"


def run_export(config: ExportConfig | None = None, *, limit: int | None = None) -> dict[str, Any]:
    cfg = config or ExportConfig()
    cfg.paths.export_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting DeepSeek export.")
    logger.info("Export directory: %s", cfg.paths.export_dir)
    logger.info("Manifest: %s", cfg.manifest_file)

    session = build_authenticated_session()
    conversations = fetch_all_conversations(
        session,
        scripts_dir=cfg.paths.scripts_dir,
        cookie_file=cfg.paths.cookie_file,
        request_delay_sec=cfg.request_delay_sec,
        page_load_timeout_ms=cfg.page_load_timeout_ms,
    )
    if limit is not None:
        logger.info("Applying limit: first %s conversations from fetched list.", limit)
        conversations = conversations[:limit]

    manifest = load_json_manifest(cfg.manifest_file, {"last_updated": None, "conversations": []})
    manifest_entries = manifest.get("conversations", [])
    logger.info("Fetched conversations: %s", len(conversations))
    logger.info("Manifest entries: %s", len(manifest_entries))
    exported_by_id = {
        item["conversation_id"]: item for item in manifest_entries if item.get("conversation_id")
    }
    pending = [
        (item, status)
        for item in conversations
        if (status := _export_status(item, exported_by_id.get(item["conversation_id"]))) is not None
    ]

    successes = 0
    new_count = sum(1 for _, status in pending if status == "new")
    updated_count = sum(1 for _, status in pending if status == "updated")
    unchanged_count = len(conversations) - len(pending)
    logger.info(
        "Export decisions: %s new, %s updated, %s unchanged/skipped.",
        new_count,
        updated_count,
        unchanged_count,
    )
    if updated_count:
        logger.info("Updated chats are detected by comparing DeepSeek updated_at against the manifest baseline.")

    failures: list[dict[str, str]] = []
    for index, (conversation, status) in enumerate(pending, start=1):
        try:
            logger.info(
                "[%s/%s] Exporting %s chat: %s (%s)",
                index,
                len(pending),
                status,
                conversation.get("original_title", "Untitled"),
                conversation.get("conversation_id", "")[:8],
            )
            messages = fetch_messages(
                session,
                conversation["conversation_id"],
                conversation["url"],
                scripts_dir=cfg.paths.scripts_dir,
                cookie_file=cfg.paths.cookie_file,
                page_load_timeout_ms=cfg.page_load_timeout_ms,
            )
            previous_entry = exported_by_id.get(conversation["conversation_id"])
            entry = write_exported_conversation(cfg.paths.export_dir, conversation, messages)
            _remove_replaced_export_file(cfg.paths.export_dir, previous_entry, entry)
            _upsert_manifest_entry(manifest, entry)
            exported_by_id[conversation["conversation_id"]] = entry
            successes += 1
            save_json_manifest(cfg.manifest_file, manifest)
            logger.info("Wrote export: %s", entry.get("file_name", ""))
        except Exception as exc:
            logger.info(
                "Failed to export %s chat %s: %s",
                status,
                conversation.get("conversation_id", "")[:8],
                exc,
            )
            failures.append(
                {
                    "conversation_id": conversation.get("conversation_id", ""),
                    "title": conversation.get("original_title", ""),
                    "status": status,
                    "error": str(exc),
                }
            )

        if index < len(pending):
            time.sleep(cfg.request_delay_sec)

    if failures:
        cfg.failure_log.write_text(
            "\n".join(
                f"{item['conversation_id']} | {item['status']} | {item['title']} | {item['error']}"
                for item in failures
            )
            + "\n",
            encoding="utf-8",
        )
        logger.info("Wrote failure log: %s", cfg.failure_log)

    logger.info("DeepSeek export finished: %s succeeded, %s failed.", successes, len(failures))

    return {
        "total_conversations": len(conversations),
        "already_exported": len(conversations) - len(pending),
        "new_to_export": len(pending),
        "new_conversations": new_count,
        "updated_conversations": updated_count,
        "succeeded": successes,
        "failed": len(failures),
        "output_dir": str(cfg.paths.export_dir),
    }


def _export_status(conversation: dict[str, Any], previous_entry: dict[str, Any] | None) -> str | None:
    if previous_entry is None:
        return "new"

    current_updated_at = _parse_timestamp(conversation.get("updated_at"))
    previous_baseline = _parse_timestamp(previous_entry.get("updated_at")) or _parse_timestamp(
        previous_entry.get("exported_at")
    )
    if current_updated_at and previous_baseline and current_updated_at > previous_baseline:
        return "updated"

    return None


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _upsert_manifest_entry(manifest: dict[str, Any], entry: dict[str, Any]) -> None:
    conversation_id = entry.get("conversation_id")
    manifest["conversations"] = [
        item for item in manifest.get("conversations", []) if item.get("conversation_id") != conversation_id
    ]
    manifest["conversations"].append(entry)


def _remove_replaced_export_file(
    export_dir: Path,
    previous_entry: dict[str, Any] | None,
    new_entry: dict[str, Any],
) -> None:
    previous_name = previous_entry.get("file_name") if previous_entry else None
    new_name = new_entry.get("file_name")
    if not previous_name or previous_name == new_name:
        return

    previous_path = export_dir / str(previous_name)
    if previous_path.exists():
        previous_path.unlink()
