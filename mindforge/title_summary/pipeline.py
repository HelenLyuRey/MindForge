from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mindforge.hashing import stable_hash
from mindforge.llm.client import llm_call_json
from mindforge.llm.preflight import provider_preflight_check
from mindforge.manifests import append_jsonl, read_jsonl
from mindforge.markdown.filenames import slugify_filename
from mindforge.markdown.frontmatter import build_frontmatter, extract_frontmatter_and_body
from mindforge.title_summary.config import TitleSummaryConfig, load_config


def parse_date_from_filename(filename: str) -> str:
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", filename)
    return match.group(1) if match else ""


def ingest_exports(cfg: TitleSummaryConfig) -> list[dict[str, Any]]:
    if not cfg.export_dir.exists():
        raise FileNotFoundError(f"Missing export directory: {cfg.export_dir}")

    rows: list[dict[str, Any]] = []
    for path in sorted(cfg.export_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        frontmatter, body = extract_frontmatter_and_body(raw)
        source_modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        rows.append(
            {
                "source_file": path.name,
                "source_hash": stable_hash(raw),
                "source_modified_at": source_modified_at,
                "date": frontmatter.get("date", "") or parse_date_from_filename(path.name),
                "original_title": frontmatter.get("original_title") or frontmatter.get("title") or path.stem,
                "conversation_id": frontmatter.get("conversation_id", ""),
                "url": frontmatter.get("url", ""),
                "body": body,
            }
        )
    return rows


def generate_title(cfg: TitleSummaryConfig, body: str, original_title: str) -> str:
    user_prompt = json.dumps(
        {
            "task": "generate_title",
            "original_title": original_title,
            "chat_history": body[: cfg.max_input_chars],
            "rules": [
                "max 14 words",
                "no quotes",
                "avoid generic words like Chat/Notes",
                "avoid date-only title",
                "use dominant language of content",
            ],
            "output_schema": {"generated_title": "string"},
        },
        ensure_ascii=False,
    )
    output = llm_call_json(
        "Generate concise best-fit title for this chat history. Return JSON only.",
        user_prompt,
        config=cfg.llm,
        temperature=0.2,
    )
    title = str(output.get("generated_title", "")).strip()
    return (title or original_title or "Untitled Conversation")[:120]


def generate_summary(cfg: TitleSummaryConfig, body: str, generated_title: str) -> str:
    user_prompt = json.dumps(
        {
            "task": "generate_summary",
            "generated_title": generated_title,
            "chat_history": body[: cfg.max_input_chars],
            "rules": ["2-4 sentences", "no bullet points", "preserve asks and outcomes"],
            "output_schema": {"summary": "string"},
        },
        ensure_ascii=False,
    )
    output = llm_call_json(
        "Summarize this chat history in one short paragraph. Return JSON only.",
        user_prompt,
        config=cfg.llm,
        temperature=0.2,
    )
    summary = str(output.get("summary", "")).strip()
    return (summary or "Summary unavailable.")[:1200]


def transform_record(cfg: TitleSummaryConfig, row: dict[str, Any]) -> dict[str, Any]:
    try:
        generated_title = generate_title(cfg, row["body"], row["original_title"])
        summary = generate_summary(cfg, row["body"], generated_title)
        error = ""
    except Exception as exc:
        generated_title = row["original_title"] or "Untitled Conversation"
        summary = "Summary unavailable due to model timeout or parse error."
        error = str(exc)[:300]

    return {**row, "generated_title": generated_title, "summary": summary, "error": error}


def validate_records(rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("No transformed rows to validate")

    required = {"source_file", "original_title", "generated_title", "summary", "body"}
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        missing = [key for key in required if not row.get(key)]
        if missing:
            raise ValueError(f"Row {index} missing required fields: {missing}")
        if row["source_file"] in seen:
            raise ValueError(f"Duplicate source_file found after dedup: {row['source_file']}")
        seen.add(row["source_file"])


def publish_rows(
    cfg: TitleSummaryConfig,
    rows: list[dict[str, Any]],
    *,
    overwrite: bool = False,
) -> list[dict[str, str]]:
    cfg.intermediate_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[dict[str, str]] = []
    for row in rows:
        prefix = f"{row.get('date', '')} " if row.get("date") else ""
        filename = f"{prefix}{slugify_filename(_title_for_filename(row))}.md"
        previous_output_file = str(row.get("_previous_output_file", ""))
        if previous_output_file == filename:
            path = cfg.intermediate_dir / filename
        else:
            path = _dedupe_path(cfg.intermediate_dir / filename, overwrite=overwrite)
        content = build_frontmatter(
            row,
            [
                "date",
                "original_title",
                "conversation_id",
                "url",
                "generated_title",
                "summary",
                "source_file",
                "source_hash",
            ],
        )
        path.write_text(content + "\n\n" + row["body"].lstrip("\n"), encoding="utf-8")
        _remove_replaced_output(cfg.intermediate_dir, row, path)
        outputs.append({"source_file": row["source_file"], "output_file": path.name})
    return outputs


def run_pipeline(
    cfg: TitleSummaryConfig | None = None,
    *,
    limit: int | None = None,
    overwrite: bool = False,
    checkpoint_file: str = "_pipeline_results.jsonl",
    resume_from_checkpoint: bool = True,
) -> dict[str, Any]:
    cfg = cfg or load_config()
    cfg.intermediate_dir.mkdir(parents=True, exist_ok=True)
    provider_preflight_check(config=cfg.llm)

    checkpoint_path = cfg.intermediate_dir / checkpoint_file
    completed = _read_completed_records(checkpoint_path) if resume_from_checkpoint else {}
    rows = ingest_exports(cfg)
    if limit is not None:
        rows = rows[:limit]
    total_sources = len(rows)
    new_count = sum(1 for row in rows if row["source_file"] not in completed)
    updated_count = sum(
        1 for row in rows if row["source_file"] in completed and _needs_processing(row, completed)
    )
    if completed:
        rows = [_attach_previous_output(row, completed) for row in rows if _needs_processing(row, completed)]
    skipped_count = total_sources - len(rows)

    started = datetime.now(timezone.utc)
    output_count = 0
    failure_count = 0
    samples: list[dict[str, str]] = []

    for row in rows:
        try:
            transformed = [transform_record(cfg, row)]
            validate_records(transformed)
            published = publish_rows(cfg, transformed, overwrite=overwrite)
            output_count += 1
            if len(samples) < 5:
                samples.append(published[0])
            append_jsonl(
                checkpoint_path,
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "ok",
                    "source_file": row.get("source_file", ""),
                    "source_hash": row.get("source_hash", ""),
                    "source_modified_at": row.get("source_modified_at", ""),
                    "output_file": published[0].get("output_file", ""),
                    "generated_title": transformed[0].get("generated_title", ""),
                    "summary": transformed[0].get("summary", ""),
                    "error": transformed[0].get("error", ""),
                },
            )
        except Exception as exc:
            failure_count += 1
            append_jsonl(
                checkpoint_path,
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "failed",
                    "source_file": row.get("source_file", ""),
                    "source_hash": row.get("source_hash", ""),
                    "error": str(exc)[:500],
                },
            )

    return {
        "started_at": started.isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "input_count": len(rows),
        "total_sources": total_sources,
        "new_sources": new_count,
        "updated_sources": updated_count,
        "skipped_unchanged": skipped_count,
        "output_count": output_count,
        "failure_count": failure_count,
        "checkpoint_file": str(checkpoint_path),
        "sample": samples,
    }


def _read_completed_records(checkpoint_path: Path) -> dict[str, dict[str, Any]]:
    completed: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(checkpoint_path):
        source_file = str(row.get("source_file", ""))
        if row.get("status") == "ok" and source_file:
            completed[source_file] = row
    return completed


def _needs_processing(row: dict[str, Any], completed: dict[str, dict[str, Any]]) -> bool:
    previous = completed.get(str(row.get("source_file", "")))
    if previous is None:
        return True

    previous_hash = str(previous.get("source_hash", ""))
    if previous_hash:
        return previous_hash != row.get("source_hash")

    previous_timestamp = _parse_timestamp(previous.get("timestamp"))
    source_modified_at = _parse_timestamp(row.get("source_modified_at"))
    if previous_timestamp and source_modified_at:
        return source_modified_at > previous_timestamp

    return False


def _attach_previous_output(
    row: dict[str, Any],
    completed: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    previous = completed.get(str(row.get("source_file", ""))) or {}
    return {**row, "_previous_output_file": previous.get("output_file", "")}


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _remove_replaced_output(intermediate_dir: Path, row: dict[str, Any], new_path: Path) -> None:
    previous_output_file = str(row.get("_previous_output_file", ""))
    if not previous_output_file or previous_output_file == new_path.name:
        return

    previous_path = intermediate_dir / previous_output_file
    if previous_path.exists():
        previous_path.unlink()


def _title_for_filename(row: dict[str, Any]) -> str:
    title = str(row.get("generated_title", "")).strip()
    title = re.sub(r"^\d{4}-\d{2}-\d{2}\s*", "", title).strip("- _")
    return title or str(row.get("original_title", "")).strip() or "untitled"


def _dedupe_path(path: Path, *, overwrite: bool) -> Path:
    if overwrite or not path.exists():
        return path

    stem, suffix = path.stem, path.suffix
    index = 2
    while True:
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1
