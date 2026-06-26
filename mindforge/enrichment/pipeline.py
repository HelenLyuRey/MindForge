from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mindforge.config import get_paths, load_project_env, optional_path_from_env
from mindforge.enrichment.render import render_enriched_markdown
from mindforge.hashing import stable_hash
from mindforge.llm.client import LLMConfig, llm_call_json
from mindforge.manifests import load_json_manifest, save_json_manifest
from mindforge.markdown.filenames import make_filename
from mindforge.markdown.frontmatter import extract_frontmatter_and_body
from mindforge.markdown.language import detect_language_simple


DEFAULT_TAG_COUNT = 3


def load_source_notes() -> list[dict[str, Any]]:
    paths = get_paths()
    if not paths.export_dir.exists():
        raise FileNotFoundError(f"Source export folder not found: {paths.export_dir}")

    notes: list[dict[str, Any]] = []
    for path in sorted(paths.export_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        frontmatter, body = extract_frontmatter_and_body(raw, strip_body=True)
        original_title = frontmatter.get("original_title") or frontmatter.get("title") or path.stem
        conversation_id = frontmatter.get("conversation_id") or path.stem
        notes.append(
            {
                "source_key": conversation_id,
                "path": str(path.relative_to(paths.project_root)),
                "filename": path.name,
                "conversation_id": conversation_id,
                "date": frontmatter.get("date", path.stem.split(" ", 1)[0]),
                "url": frontmatter.get("url", ""),
                "original_title": original_title,
                "body": body,
                "language": detect_language_simple(body),
                "content_hash": stable_hash(raw),
            }
        )
    return notes


def load_taxonomy(taxonomy_file: Path | None = None) -> dict[str, Any]:
    paths = get_paths()
    target_file = taxonomy_file or paths.taxonomy_file
    if not target_file.exists():
        raise FileNotFoundError(f"Taxonomy file not found: {target_file}")

    taxonomy = json.loads(target_file.read_text(encoding="utf-8"))
    categories = taxonomy.get("categories", [])
    if not categories:
        raise ValueError("Taxonomy file has no categories")

    taxonomy["category_ids"] = [category["category_id"] for category in categories]
    taxonomy["category_lookup"] = {category["category_id"]: category for category in categories}
    taxonomy["taxonomy_hash"] = stable_hash(json.dumps(categories, ensure_ascii=False, sort_keys=True))
    return taxonomy


def enrich_one_note(
    note: dict[str, Any],
    taxonomy: dict[str, Any],
    *,
    llm_config: LLMConfig | None = None,
    tag_count: int = DEFAULT_TAG_COUNT,
) -> dict[str, Any]:
    max_body_chars = int(os.getenv("ENRICH_MAX_BODY_CHARS", "50000"))
    categories = taxonomy["categories"]
    category_ids = taxonomy["category_ids"]
    category_lookup = taxonomy["category_lookup"]

    user_prompt = json.dumps(
        {
            "task": "Classify one exported DeepSeek conversation and rewrite its title",
            "tag_count_target": tag_count,
            "rules": [
                "Read the conversation history before choosing tags",
                "Choose only category_id values from the taxonomy",
                "Return 2 to 4 tags unless the content is truly unclear",
                "The refined title should help a future reader find the note quickly",
                "Do not invent topics that are not supported by the conversation text",
            ],
            "taxonomy": categories,
            "document": {
                "original_title": note["original_title"],
                "language": note["language"],
                "conversation_markdown": note["body"][:max_body_chars],
            },
            "output_schema": {
                "refined_title": "string",
                "tag_category_ids": ["enum"],
                "confidence": "0..1",
                "reason": "short string",
            },
        },
        ensure_ascii=False,
    )
    raw = llm_call_json(
        (
            "You rewrite conversation note titles and assign taxonomy tags. Return strict JSON only. "
            "Use only category_id values from the provided taxonomy. "
            "Prefer 2 to 4 tags, avoid generic titles, and keep the refined title concise but descriptive."
        ),
        user_prompt,
        config=llm_config,
        temperature=0.0,
    )

    tag_category_ids = _valid_tag_ids(raw.get("tag_category_ids"), category_ids)
    if not tag_category_ids:
        tag_category_ids = [_fallback_category_id(category_ids)]
    tag_category_ids = tag_category_ids[:4]

    confidence = raw.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)):
        confidence = 0.0

    return {
        "refined_title": str(raw.get("refined_title") or note["original_title"]).strip(),
        "tag_category_ids": tag_category_ids,
        "tag_labels": [category_lookup[category_id]["label"] for category_id in tag_category_ids],
        "confidence": round(float(confidence), 4),
        "reason": str(raw.get("reason", "")).strip()[:280],
    }


def preview_one_note(
    md_path: str | None = None,
    *,
    llm_config: LLMConfig | None = None,
    tag_count: int = DEFAULT_TAG_COUNT,
) -> dict[str, Any]:
    taxonomy = load_taxonomy()
    notes = load_source_notes()
    if not notes:
        raise FileNotFoundError(f"No markdown files found in {get_paths().export_dir}")

    note = notes[0] if md_path is None else _find_note(notes, md_path)
    decision = enrich_one_note(note, taxonomy, llm_config=llm_config, tag_count=tag_count)
    return {
        "path": note["path"],
        "original_title": note["original_title"],
        "refined_title": decision["refined_title"],
        "tags": decision["tag_labels"],
        "taxonomy_category_ids": decision["tag_category_ids"],
        "confidence": decision["confidence"],
        "reason": decision["reason"],
    }


def enrich_all_notes(
    *,
    limit: int | None = None,
    force: bool = False,
    llm_config: LLMConfig | None = None,
    tag_count: int = DEFAULT_TAG_COUNT,
) -> list[dict[str, Any]]:
    load_project_env()
    paths = get_paths()
    paths.enriched_dir.mkdir(parents=True, exist_ok=True)
    obsidian_dir = _get_obsidian_output_dir()
    manifest_file = paths.enriched_dir / "enrichment_manifest.json"

    taxonomy = load_taxonomy()
    notes = load_source_notes()
    manifest = load_json_manifest(manifest_file, {"last_updated": None, "notes": []})
    existing = {entry["source_key"]: entry for entry in manifest.get("notes", [])}
    selected_notes = notes if limit is None else notes[:limit]

    results: list[dict[str, Any]] = []
    refreshed_entries: list[dict[str, Any]] = []
    for note in selected_notes:
        signature = stable_hash(note["content_hash"] + "::" + taxonomy["taxonomy_hash"])
        prior = existing.get(note["source_key"])
        if not force and prior and prior.get("signature") == signature:
            results.append(
                {
                    "status": "skipped",
                    "source_file": note["filename"],
                    "refined_title": prior.get("refined_title"),
                    "tags": prior.get("tags", []),
                }
            )
            refreshed_entries.append(prior)
            continue

        decision = enrich_one_note(note, taxonomy, llm_config=llm_config, tag_count=tag_count)
        entry = write_enriched_note(note, decision, taxonomy["taxonomy_hash"], obsidian_dir=obsidian_dir)
        refreshed_entries.append(entry)
        results.append(
            {
                "status": "updated",
                "source_file": note["filename"],
                "output_file": entry["output_file"],
                "refined_title": entry["refined_title"],
                "tags": entry["tags"],
            }
        )

    touched_keys = {note["source_key"] for note in selected_notes}
    refreshed_entries.extend(
        old_entry for old_entry in manifest.get("notes", []) if old_entry.get("source_key") not in touched_keys
    )
    manifest["notes"] = sorted(refreshed_entries, key=lambda item: item.get("source_file", ""))
    save_json_manifest(manifest_file, manifest)
    return results


def write_enriched_note(
    note: dict[str, Any],
    decision: dict[str, Any],
    taxonomy_hash: str,
    *,
    obsidian_dir: Path | None = None,
) -> dict[str, Any]:
    paths = get_paths()
    rendered = render_enriched_markdown(note, decision)
    filename = make_filename(decision["refined_title"], note["date"])
    local_path = paths.enriched_dir / filename
    local_path.write_text(rendered, encoding="utf-8")

    obsidian_path = None
    if obsidian_dir is not None:
        obsidian_path = obsidian_dir / filename
        obsidian_path.write_text(rendered, encoding="utf-8")

    return {
        "source_key": note["source_key"],
        "conversation_id": note["conversation_id"],
        "source_file": note["filename"],
        "output_file": filename,
        "local_output_path": str(local_path.relative_to(paths.project_root)),
        "obsidian_output_path": str(obsidian_path) if obsidian_path else None,
        "refined_title": decision["refined_title"],
        "tags": decision["tag_labels"],
        "taxonomy_category_ids": decision["tag_category_ids"],
        "confidence": decision["confidence"],
        "reason": decision["reason"],
        "source_hash": note["content_hash"],
        "taxonomy_hash": taxonomy_hash,
        "signature": stable_hash(note["content_hash"] + "::" + taxonomy_hash),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _get_obsidian_output_dir() -> Path | None:
    vault_path = optional_path_from_env("ENRICHED_OBSIDIAN_VAULT_PATH")
    if vault_path is None:
        return None
    subfolder = os.getenv("ENRICHED_OBSIDIAN_SUBFOLDER", "DeepSeek Tagged")
    obsidian_dir = vault_path / subfolder
    obsidian_dir.mkdir(parents=True, exist_ok=True)
    return obsidian_dir


def _find_note(notes: list[dict[str, Any]], md_path: str) -> dict[str, Any]:
    wanted = md_path.replace("\\", "/")
    note = next(
        (item for item in notes if item["path"].replace("\\", "/") == wanted or item["filename"] == Path(wanted).name),
        None,
    )
    if note is None:
        raise FileNotFoundError(f"Could not find markdown note: {md_path}")
    return note


def _valid_tag_ids(raw_ids: Any, category_ids: list[str]) -> list[str]:
    if not isinstance(raw_ids, list):
        return []

    valid_ids: list[str] = []
    for raw_id in raw_ids:
        category_id = str(raw_id).strip()
        if category_id in category_ids and category_id not in valid_ids:
            valid_ids.append(category_id)
    return valid_ids


def _fallback_category_id(category_ids: list[str]) -> str:
    if "unclear" in category_ids:
        return "unclear"
    if "other" in category_ids:
        return "other"
    return category_ids[0]
