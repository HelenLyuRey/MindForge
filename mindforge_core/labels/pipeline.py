from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from mindforge_core.hashing import stable_hash
from mindforge_core.labels.config import LabelConfig, load_config
from mindforge_core.llm.client import llm_call_json
from mindforge_core.llm.preflight import provider_preflight_check
from mindforge_core.markdown.frontmatter import build_frontmatter, extract_frontmatter_and_body

logger = logging.getLogger(__name__)

CHAT_KIND = "chat"
ALLOWED_PURPOSES = [
    "think-out-loud-reflection",
    "deep-learning",
    "creation",
    "lookup",
]
DEFAULT_PURPOSE = "lookup"

PURPOSE_GUIDE = [
    {
        "id": "think-out-loud-reflection",
        "use_when": (
            "The user is processing thoughts, feelings, identity, a decision, or a messy situation. "
            "They would reopen this later to see how they thought."
        ),
        "examples": "career vs relationship rumination, attachment processing, holiday dilemma",
    },
    {
        "id": "deep-learning",
        "use_when": (
            "The user wants to understand how a concept, framework, or domain works. "
            "They would reopen this as knowledge, not as a record of their inner life. "
            "This is a purpose label, not a machine-learning topic tag."
        ),
        "examples": "how neural networks work, insurance industry structure, sleep-stage scoring",
    },
    {
        "id": "creation",
        "use_when": (
            "The user is making an artifact: script, copy, design, prompt, slides, talking points, or a rewrite."
        ),
        "examples": "vlog script, Xiaohongshu caption, bathroom AI prompt, client POV deck",
    },
    {
        "id": "lookup",
        "use_when": (
            "One-shot research, comparison, recommendation, itinerary, packing list, or how-to. Rarely reopened."
        ),
        "examples": "flight comparison, foundation recommendation, Maldives agency table",
    },
]

FRONTMATTER_ORDER = [
    "date",
    "original_title",
    "conversation_id",
    "url",
    "generated_title",
    "summary",
    "source_file",
    "source_hash",
    "kind",
    "purpose",
    "tags",
    "classification_confidence",
    "classification_reason",
    "purpose_confidence",
    "purpose_reason",
]


def load_taxonomy_tags(cfg: LabelConfig) -> dict[str, Any]:
    if not cfg.taxonomy_file.exists():
        raise FileNotFoundError(f"Taxonomy file not found: {cfg.taxonomy_file}")

    taxonomy = json.loads(cfg.taxonomy_file.read_text(encoding="utf-8"))
    categories = taxonomy.get("categories", [])
    if not categories:
        raise ValueError("Taxonomy file has no categories")

    flat_tags: list[str] = []
    for category in categories:
        label = str(category.get("label") or category.get("category_id", "")).strip()
        if label:
            flat_tags.append(label)
        for subtopic in category.get("subtopics", []):
            value = str(subtopic).strip()
            if value:
                flat_tags.append(value)

    taxonomy["flat_tags"] = _unique_preserving_order(flat_tags)
    taxonomy["taxonomy_hash"] = stable_hash(json.dumps(categories, ensure_ascii=False, sort_keys=True))
    return taxonomy


def ingest_intermediate_markdowns(cfg: LabelConfig) -> list[dict[str, Any]]:
    if not cfg.intermediate_dir.exists():
        raise FileNotFoundError(f"Missing intermediate markdown directory: {cfg.intermediate_dir}")

    rows: list[dict[str, Any]] = []
    for path in sorted(cfg.intermediate_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        frontmatter, body = extract_frontmatter_and_body(raw)
        frontmatter = _normalize_frontmatter_values(frontmatter)
        rows.append(
            {
                "path": path,
                "filename": path.name,
                "frontmatter": frontmatter,
                "body": body.strip(),
                "title": frontmatter.get("generated_title")
                or frontmatter.get("original_title")
                or path.stem,
                "summary": frontmatter.get("summary", ""),
                "source_hash": stable_hash(raw),
            }
        )
    return rows


def label_record(cfg: LabelConfig, row: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    return _label_record_with_document(
        cfg,
        row,
        taxonomy,
        {
            "generated_title": row["frontmatter"].get("generated_title", ""),
            "original_title": row["frontmatter"].get("original_title", ""),
            "summary": row["summary"],
            "markdown_body": row["body"][: cfg.max_input_chars],
        },
        system_prompt=(
            "You assign Obsidian-ready tags from a fixed Chinese taxonomy. "
            "Return strict JSON only. Tags must be exact strings from allowed_tags."
        ),
    )


def label_record_fallback(cfg: LabelConfig, row: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    return _label_record_with_document(
        cfg,
        row,
        taxonomy,
        {
            "generated_title": row["frontmatter"].get("generated_title", ""),
            "original_title": row["frontmatter"].get("original_title", ""),
            "summary": row["summary"],
        },
        system_prompt=(
            "You assign Obsidian-ready tags from a fixed Chinese taxonomy. "
            "Return strict JSON only. Use only the document title and summary for tag matching; do not rely on the full markdown body."
        ),
    )


def _label_record_with_document(
    cfg: LabelConfig,
    row: dict[str, Any],
    taxonomy: dict[str, Any],
    document: dict[str, Any],
    system_prompt: str,
) -> dict[str, Any]:
    allowed_tags = taxonomy["flat_tags"]
    user_prompt = json.dumps(
        {
            "task": "Match taxonomy labels and subtopics to one markdown note as Obsidian tags",
            "max_tags": cfg.max_tags,
            "rules": [
                "Return flat tags only; do not create hierarchy or nested tags.",
                f"Choose only the top {cfg.max_tags} strongest taxonomy labels/subtopics.",
                "Use category labels and subtopics as equal tags.",
                "Use only exact strings from allowed_tags.",
                "Do not invent, translate, merge, or rename tags.",
                "Rank tags from strongest to weakest match.",
                "Do not assign purpose values; tags are the topic layer only.",
            ],
            "allowed_tags": allowed_tags,
            "taxonomy_context": taxonomy["categories"],
            "document": document,
            "output_schema": {
                "tags": [f"up to {cfg.max_tags} exact allowed tag strings"],
                "confidence": "0..1",
                "reason": "short string explaining the strongest matches",
            },
        },
        ensure_ascii=False,
    )
    output = llm_call_json(system_prompt, user_prompt, config=cfg.llm, temperature=0.0)

    tags = _valid_choice_list(output.get("tags"), allowed_tags)[: cfg.max_tags]
    if not tags:
        tags = [allowed_tags[0]]

    return {
        "tags": tags,
        "confidence": _as_confidence(output.get("confidence")),
        "reason": str(output.get("reason", "")).strip()[:280],
    }


def classify_purpose(cfg: LabelConfig, row: dict[str, Any]) -> dict[str, Any]:
    user_prompt = json.dumps(
        {
            "task": "Assign purpose labels for one chat note",
            "max_purposes": cfg.max_purposes,
            "rules": [
                "Purpose is how the chat was used, not what topic it is about.",
                "Do not infer purpose from topic tags or life domains.",
                "deep-learning means the user wanted to understand a concept; it is not an AI/ML topic tag.",
                f"Choose 1 purpose, or 2 if the chat clearly mixes purposes. Never more than {cfg.max_purposes}.",
                "Use only exact strings from allowed_purposes.",
                "Do not invent, translate, merge, or rename purposes.",
                "Ask: months later, would they reopen this to see their past self, the knowledge, the artifact, or not at all?",
            ],
            "allowed_purposes": ALLOWED_PURPOSES,
            "purpose_guide": PURPOSE_GUIDE,
            "document": {
                "generated_title": row["frontmatter"].get("generated_title", ""),
                "original_title": row["frontmatter"].get("original_title", ""),
                "summary": row["summary"],
            },
            "output_schema": {
                "purpose": [f"up to {cfg.max_purposes} exact allowed purpose strings"],
                "confidence": "0..1",
                "reason": "short string explaining the strongest matches",
            },
        },
        ensure_ascii=False,
    )
    output = llm_call_json(
        (
            "You assign chat-purpose labels from a fixed English vocabulary. "
            "Return strict JSON only. Purpose values must be exact strings from allowed_purposes."
        ),
        user_prompt,
        config=cfg.llm,
        temperature=0.0,
    )

    purpose = _valid_choice_list(output.get("purpose"), ALLOWED_PURPOSES)[: cfg.max_purposes]
    if not purpose:
        purpose = [DEFAULT_PURPOSE]

    return {
        "purpose": purpose,
        "purpose_confidence": _as_confidence(output.get("confidence")),
        "purpose_reason": str(output.get("reason", "")).strip()[:280],
    }


def publish_record(cfg: LabelConfig, row: dict[str, Any], decision: dict[str, Any]) -> dict[str, Path | None]:
    cfg.final_dir.mkdir(parents=True, exist_ok=True)
    rendered = render_tagged_markdown(row, decision)
    output_path = cfg.final_dir / row["filename"]
    output_path.write_text(rendered, encoding="utf-8")
    return {
        "output_path": output_path,
        "obsidian_path": write_obsidian_copy(cfg, row["filename"], rendered),
    }


def write_obsidian_copy(cfg: LabelConfig, filename: str, content: str) -> Path | None:
    obsidian_dir = get_obsidian_output_dir(cfg)
    if obsidian_dir is None:
        return None

    obsidian_path = obsidian_dir / filename
    obsidian_path.write_text(content, encoding="utf-8")
    return obsidian_path


def sync_existing_to_obsidian(cfg: LabelConfig, output_path: Path) -> Path | None:
    if cfg.obsidian_vault_path is None:
        return None
    return write_obsidian_copy(cfg, output_path.name, output_path.read_text(encoding="utf-8"))


def get_obsidian_output_dir(cfg: LabelConfig) -> Path | None:
    if cfg.obsidian_vault_path is None:
        return None

    output_dir = cfg.obsidian_vault_path / cfg.obsidian_chats_folder
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def render_tagged_markdown(row: dict[str, Any], decision: dict[str, Any]) -> str:
    frontmatter = dict(row["frontmatter"])
    frontmatter["kind"] = CHAT_KIND
    frontmatter["purpose"] = decision["purpose"]
    frontmatter["tags"] = decision["tags"]
    frontmatter["classification_confidence"] = decision["confidence"]
    frontmatter["classification_reason"] = decision["reason"]
    frontmatter["purpose_confidence"] = decision["purpose_confidence"]
    frontmatter["purpose_reason"] = decision["purpose_reason"]

    ordered_keys = [key for key in FRONTMATTER_ORDER if key in frontmatter]
    ordered_keys.extend(key for key in frontmatter if key not in ordered_keys)
    return f"{build_frontmatter(frontmatter, ordered_keys)}\n\n{row['body'].strip()}\n"


def run_pipeline(
    cfg: LabelConfig | None = None,
    *,
    path: str | None = None,
    limit: int | None = None,
    force: bool = False,
    preview: bool = False,
    purpose_only: bool = False,
) -> list[dict[str, Any]]:
    cfg = cfg or load_config()
    provider_preflight_check(config=cfg.llm)
    taxonomy = load_taxonomy_tags(cfg)
    rows = ingest_intermediate_markdowns(cfg)
    if not rows:
        raise FileNotFoundError(f"No markdown files found in {cfg.intermediate_dir}")

    selected = [_find_row(cfg, rows, path)] if path else rows
    if limit is not None:
        selected = selected[:limit]

    results: list[dict[str, Any]] = []
    failed_rows: list[tuple[dict[str, Any], str]] = []
    total_to_process = len(selected)
    for index, row in enumerate(selected, start=1):
        output_path = cfg.final_dir / row["filename"]
        existing = _read_existing_output(output_path)
        need_tags, need_purpose = _needed_updates(
            existing,
            force=force,
            preview=preview,
            purpose_only=purpose_only,
        )

        if existing and not need_tags and not need_purpose and not preview:
            if existing.get("kind") != CHAT_KIND:
                decision = _decision_from_existing(existing)
                published = publish_record(cfg, row, decision)
                output_path = published["output_path"] or output_path
                results.append(
                    _result_row(
                        cfg,
                        row,
                        decision,
                        status="updated",
                        output_path=output_path,
                        obsidian_path=published["obsidian_path"],
                        updated_fields=["kind"],
                    )
                )
                continue

            obsidian_path = sync_existing_to_obsidian(cfg, output_path)
            results.append(
                {
                    "status": "skipped",
                    "source_file": row["filename"],
                    "output_file": str(output_path.relative_to(cfg.project_root)),
                    "obsidian_output_file": str(obsidian_path) if obsidian_path else None,
                    "reason": "output exists with kind, purpose, and tags; use --force or --purpose-only to rebuild",
                }
            )
            logger.info("Skipped %d/%d: %s (%s)", index, total_to_process, row["filename"], "output exists")
            continue

        try:
            decision = label_record(cfg, row, taxonomy)
        except Exception as exc:
            failed_rows.append((row, str(exc)))
            logger.warning("Failed %d/%d: %s (%s)", index, total_to_process, row["filename"], exc)
            continue

        # Recompute only what's needed; reuse existing frontmatter values when available.
        if need_tags:
            tag_decision = label_record(cfg, row, taxonomy)
        else:
            tag_decision = {
                "tags": existing["tags"] if existing else [],
                "confidence": _as_confidence(existing.get("classification_confidence") if existing else 0.0),
                "reason": str(existing.get("classification_reason", "") if existing else ""),
            }

        if need_purpose:
            purpose_decision = classify_purpose(cfg, row)
        else:
            purpose_decision = {
                "purpose": existing["purpose"] if existing else [DEFAULT_PURPOSE],
                "purpose_confidence": _as_confidence(
                    existing.get("purpose_confidence") if existing else 0.0
                ),
                "purpose_reason": str(existing.get("purpose_reason", "") if existing else ""),
            }

        decision = {**tag_decision, **purpose_decision}

        published: dict[str, Path | None] = {"output_path": None, "obsidian_path": None}
        if not preview:
            published = publish_record(cfg, row, decision)
            output_path = published["output_path"] or output_path

        updated_fields = [field for field, needed in (("tags", need_tags), ("purpose", need_purpose)) if needed]
        if existing is None or existing.get("kind") != CHAT_KIND:
            updated_fields.append("kind")

        results.append(
            _result_row(
                cfg,
                row,
                decision,
                status="preview" if preview else "updated",
                output_path=None if preview else output_path,
                obsidian_path=None if preview else published["obsidian_path"],
                updated_fields=updated_fields,
            )
        )
        logger.info(
            "Processed %d/%d: %s -> %s",
            index,
            total_to_process,
            row["filename"],
            "preview" if preview else (published["output_path"].name if published["output_path"] else output_path.name),
        )

    if failed_rows and not preview:
        logger.info("Retrying %d failed rows with fallback labeling...", len(failed_rows))
        for row, first_error in failed_rows:
            try:
                decision = label_record_fallback(cfg, row, taxonomy)
            except Exception as exc:
                logger.error(
                    "Fallback failed for %s after initial failure (%s): %s",
                    row["filename"],
                    first_error,
                    exc,
                )
                results.append(
                    {
                        "status": "failed",
                        "source_file": row["filename"],
                        "output_file": None,
                        "obsidian_output_file": None,
                        "tags": [],
                        "confidence": 0.0,
                        "reason": f"Initial: {first_error}; fallback: {exc}",
                    }
                )
                continue

            published = publish_record(cfg, row, decision)
            output_path = published["output_path"] or (cfg.final_dir / row["filename"])
            results.append(
                {
                    "status": "fallback",
                    "source_file": row["filename"],
                    "output_file": str(output_path.relative_to(cfg.project_root)),
                    "obsidian_output_file": str(published["obsidian_path"]) if published["obsidian_path"] else None,
                    "tags": decision["tags"],
                    "confidence": decision["confidence"],
                    "reason": f"fallback after initial failure: {first_error}",
                }
            )
            logger.info(
                "Fallback processed: %s -> %s",
                row["filename"],
                published["output_path"].name if published["output_path"] else row["filename"],
            )

    if failed_rows:
        failed_list = [f"{row['filename']}: {row['frontmatter'].get('generated_title', row['frontmatter'].get('original_title', row['filename']))}" for row, _ in failed_rows]
        logger.info("Failed rows after Stage 3 initial pass: %s", failed_list)

    return results


def _needed_updates(
    existing: dict[str, Any] | None,
    *,
    force: bool,
    preview: bool,
    purpose_only: bool,
) -> tuple[bool, bool]:
    has_tags = bool(existing and existing.get("tags"))
    has_purpose = bool(existing and existing.get("purpose"))
    if purpose_only:
        return (not has_tags), True
    if preview or force:
        return True, True
    return (not has_tags, not has_purpose)


def _read_existing_output(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None

    raw = path.read_text(encoding="utf-8", errors="ignore")
    frontmatter, _ = extract_frontmatter_and_body(raw)
    frontmatter = _normalize_frontmatter_values(frontmatter)
    return {
        "kind": str(frontmatter.get("kind", "")).strip(),
        "purpose": _valid_choice_list(frontmatter.get("purpose"), ALLOWED_PURPOSES),
        "tags": _as_str_list(frontmatter.get("tags")),
        "classification_confidence": frontmatter.get("classification_confidence", ""),
        "classification_reason": frontmatter.get("classification_reason", ""),
        "purpose_confidence": frontmatter.get("purpose_confidence", ""),
        "purpose_reason": frontmatter.get("purpose_reason", ""),
    }


def _decision_from_existing(existing: dict[str, Any]) -> dict[str, Any]:
    return {
        "tags": existing.get("tags") or [],
        "confidence": _as_confidence(existing.get("classification_confidence")),
        "reason": str(existing.get("classification_reason", "")),
        "purpose": existing.get("purpose") or [DEFAULT_PURPOSE],
        "purpose_confidence": _as_confidence(existing.get("purpose_confidence")),
        "purpose_reason": str(existing.get("purpose_reason", "")),
    }


def _result_row(
    cfg: LabelConfig,
    row: dict[str, Any],
    decision: dict[str, Any],
    *,
    status: str,
    output_path: Path | None,
    obsidian_path: Path | None,
    updated_fields: list[str],
) -> dict[str, Any]:
    return {
        "status": status,
        "source_file": row["filename"],
        "output_file": None if output_path is None else str(output_path.relative_to(cfg.project_root)),
        "obsidian_output_file": None if obsidian_path is None else str(obsidian_path),
        "kind": CHAT_KIND,
        "purpose": decision["purpose"],
        "tags": decision["tags"],
        "confidence": decision["confidence"],
        "reason": decision["reason"],
        "purpose_confidence": decision["purpose_confidence"],
        "purpose_reason": decision["purpose_reason"],
        "updated_fields": updated_fields,
    }


def _find_row(cfg: LabelConfig, rows: list[dict[str, Any]], md_path: str) -> dict[str, Any]:
    wanted = md_path.replace("\\", "/")
    row = next(
        (
            item
            for item in rows
            if item["filename"] == Path(wanted).name
            or str(item["path"].relative_to(cfg.project_root)).replace("\\", "/") == wanted
        ),
        None,
    )
    if row is None:
        raise FileNotFoundError(f"Could not find markdown note: {md_path}")
    return row


def _valid_choice_list(raw_values: Any, allowed_values: list[str]) -> list[str]:
    allowed = set(allowed_values)
    valid_values: list[str] = []
    for raw_value in _as_str_list(raw_values):
        value = raw_value.strip()
        if value in allowed and value not in valid_values:
            valid_values.append(value)
    return valid_values


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _as_confidence(value: Any) -> float:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return 0.0


def _normalize_frontmatter_values(frontmatter: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in frontmatter.items():
        if isinstance(value, list):
            normalized[key] = [str(item).replace('\\"', '"') for item in value]
        else:
            normalized[key] = str(value).replace('\\"', '"')
    return normalized


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            unique.append(value)
            seen.add(value)
    return unique
