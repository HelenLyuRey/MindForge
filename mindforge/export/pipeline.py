from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mindforge.config import ProjectPaths, get_paths
from mindforge.export.api import fetch_all_conversations, fetch_messages
from mindforge.export.auth import build_authenticated_session
from mindforge.export.writer import write_exported_conversation
from mindforge.manifests import load_json_manifest, save_json_manifest


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

    session = build_authenticated_session()
    conversations = fetch_all_conversations(
        session,
        scripts_dir=cfg.paths.scripts_dir,
        cookie_file=cfg.paths.cookie_file,
        request_delay_sec=cfg.request_delay_sec,
        page_load_timeout_ms=cfg.page_load_timeout_ms,
    )
    if limit is not None:
        conversations = conversations[:limit]

    manifest = load_json_manifest(cfg.manifest_file, {"last_updated": None, "conversations": []})
    exported_ids = {item["conversation_id"] for item in manifest.get("conversations", [])}
    pending = [item for item in conversations if item["conversation_id"] not in exported_ids]

    successes = 0
    failures: list[dict[str, str]] = []
    for index, conversation in enumerate(pending, start=1):
        try:
            messages = fetch_messages(
                session,
                conversation["conversation_id"],
                conversation["url"],
                scripts_dir=cfg.paths.scripts_dir,
                cookie_file=cfg.paths.cookie_file,
                page_load_timeout_ms=cfg.page_load_timeout_ms,
            )
            manifest["conversations"].append(
                write_exported_conversation(cfg.paths.export_dir, conversation, messages)
            )
            successes += 1
            save_json_manifest(cfg.manifest_file, manifest)
        except Exception as exc:
            failures.append(
                {
                    "conversation_id": conversation.get("conversation_id", ""),
                    "title": conversation.get("original_title", ""),
                    "error": str(exc),
                }
            )

        if index < len(pending):
            time.sleep(cfg.request_delay_sec)

    if failures:
        cfg.failure_log.write_text(
            "\n".join(
                f"{item['conversation_id']} | {item['title']} | {item['error']}" for item in failures
            )
            + "\n",
            encoding="utf-8",
        )

    return {
        "total_conversations": len(conversations),
        "already_exported": len(conversations) - len(pending),
        "new_to_export": len(pending),
        "succeeded": successes,
        "failed": len(failures),
        "output_dir": str(cfg.paths.export_dir),
    }
