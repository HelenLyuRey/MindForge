from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mindforge_core.hashing import stable_hash
from mindforge_core.labels.config import LabelConfig, load_config
from mindforge_core.llm.client import llm_call_json
from mindforge_core.llm.preflight import provider_preflight_check
from mindforge_core.markdown.frontmatter import build_frontmatter, extract_frontmatter_and_body


FRONTMATTER_ORDER = [
    "date",
    "original_title",
    "conversation_id",
    "url",
    "generated_title",
    "summary",
    "source_file",
    "source_hash",
    "tags",
    "classification_confidence",
    "classification_reason",
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
            ],
            "allowed_tags": allowed_tags,
            "taxonomy_context": taxonomy["categories"],
            "document": {
                "generated_title": row["frontmatter"].get("generated_title", ""),
                "original_title": row["frontmatter"].get("original_title", ""),
                "summary": row["summary"],
                "markdown_body": row["body"][: cfg.max_input_chars],
            },
            "output_schema": {
                "tags": [f"up to {cfg.max_tags} exact allowed tag strings"],
                "confidence": "0..1",
                "reason": "short string explaining the strongest matches",
            },
        },
        ensure_ascii=False,
    )
    output = llm_call_json(
        (
            "You assign Obsidian-ready tags from a fixed Chinese taxonomy. "
            "Return strict JSON only. Tags must be exact strings from allowed_tags."
        ),
        user_prompt,
        config=cfg.llm,
        temperature=0.0,
    )

    tags = _valid_tags(output.get("tags"), allowed_tags)[: cfg.max_tags]
    if not tags:
        tags = [allowed_tags[0]]

    confidence = output.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)):
        confidence = 0.0

    return {
        "tags": tags,
        "confidence": round(float(confidence), 4),
        "reason": str(output.get("reason", "")).strip()[:280],
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

    output_dir = cfg.obsidian_vault_path
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def render_tagged_markdown(row: dict[str, Any], decision: dict[str, Any]) -> str:
    frontmatter = dict(row["frontmatter"])
    frontmatter["tags"] = decision["tags"]
    frontmatter["classification_confidence"] = decision["confidence"]
    frontmatter["classification_reason"] = decision["reason"]

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
    for row in selected:
        output_path = cfg.final_dir / row["filename"]
        if output_path.exists() and not force and not preview:
            obsidian_path = sync_existing_to_obsidian(cfg, output_path)
            results.append(
                {
                    "status": "skipped",
                    "source_file": row["filename"],
                    "output_file": str(output_path.relative_to(cfg.project_root)),
                    "obsidian_output_file": str(obsidian_path) if obsidian_path else None,
                    "reason": "output exists; use --force to rebuild",
                }
            )
            continue

        decision = label_record(cfg, row, taxonomy)
        published: dict[str, Path | None] = {"output_path": None, "obsidian_path": None}
        if not preview:
            published = publish_record(cfg, row, decision)
            output_path = published["output_path"] or output_path

        results.append(
            {
                "status": "preview" if preview else "updated",
                "source_file": row["filename"],
                "output_file": None if preview else str(output_path.relative_to(cfg.project_root)),
                "obsidian_output_file": None
                if preview or published["obsidian_path"] is None
                else str(published["obsidian_path"]),
                "tags": decision["tags"],
                "confidence": decision["confidence"],
                "reason": decision["reason"],
            }
        )
    return results


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


def _valid_tags(raw_tags: Any, allowed_tags: list[str]) -> list[str]:
    if not isinstance(raw_tags, list):
        return []

    allowed = set(allowed_tags)
    valid_tags: list[str] = []
    for raw_tag in raw_tags:
        tag = str(raw_tag).strip()
        if tag in allowed and tag not in valid_tags:
            valid_tags.append(tag)
    return valid_tags


def _normalize_frontmatter_values(frontmatter: dict[str, str]) -> dict[str, str]:
    return {key: value.replace('\\"', '"') for key, value in frontmatter.items()}


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            unique.append(value)
            seen.add(value)
    return unique
