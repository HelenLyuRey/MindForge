from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mindforge.config import get_paths
from mindforge.llm.client import LLMConfig, llm_call_json
from mindforge.markdown.frontmatter import extract_frontmatter_and_body
from mindforge.markdown.language import detect_language_simple


def clean_snippet(text: str, max_chars: int = 6000) -> str:
    return re.sub(r"\s+", " ", text).strip()[:max_chars]


def tag_one_markdown(
    md_path: str | Path | None = None,
    *,
    taxonomy_file: Path | None = None,
    llm_config: LLMConfig | None = None,
) -> dict[str, Any]:
    paths = get_paths()
    target_taxonomy_file = taxonomy_file or paths.taxonomy_file
    if not target_taxonomy_file.exists():
        raise FileNotFoundError(f"Taxonomy file not found: {target_taxonomy_file}")

    taxonomy = json.loads(target_taxonomy_file.read_text(encoding="utf-8"))
    categories = taxonomy.get("categories", [])
    category_ids = [category["category_id"] for category in categories]
    if not category_ids:
        raise ValueError("Taxonomy has no categories")

    picked = _pick_markdown_path(md_path)
    raw = picked.read_text(encoding="utf-8", errors="ignore")
    frontmatter, body = extract_frontmatter_and_body(raw)
    doc = {
        "path": str(picked.relative_to(paths.project_root)),
        "title": frontmatter.get("title") or frontmatter.get("original_title") or picked.stem,
        "language": detect_language_simple(body),
        "snippet": clean_snippet(body),
    }

    user_prompt = json.dumps(
        {
            "task": "Classify one markdown note",
            "category_enum": category_ids,
            "categories": categories,
            "document": doc,
            "output_schema": {
                "primary_category_id": "enum",
                "secondary_category_id": "enum|null",
                "confidence": "0..1",
                "reason": "short sentence",
            },
        },
        ensure_ascii=False,
    )
    output = llm_call_json(
        "You are a strict classifier. Return JSON only. Choose category_id from the provided enum only.",
        user_prompt,
        config=llm_config,
        temperature=0.0,
    )

    primary = output.get("primary_category_id")
    if primary not in category_ids:
        primary = "unclear" if "unclear" in category_ids else category_ids[0]

    secondary = output.get("secondary_category_id")
    if secondary not in category_ids:
        secondary = None

    confidence = output.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)):
        confidence = 0.0

    id_to_label = {category["category_id"]: category["label"] for category in categories}
    return {
        "path": doc["path"],
        "title": doc["title"],
        "language": doc["language"],
        "primary_category_id": primary,
        "primary_label": id_to_label.get(primary, primary),
        "secondary_category_id": secondary,
        "secondary_label": id_to_label.get(secondary, secondary) if secondary else None,
        "confidence": round(float(confidence), 4),
        "reason": str(output.get("reason", ""))[:240],
    }


def _pick_markdown_path(md_path: str | Path | None) -> Path:
    paths = get_paths()
    if md_path is None:
        candidates = sorted(paths.export_dir.glob("*.md"))
        if not candidates:
            raise FileNotFoundError(f"No markdown files found in {paths.export_dir}")
        return candidates[0]

    picked = Path(md_path)
    if not picked.is_absolute():
        picked = paths.project_root / picked
    if not picked.exists():
        raise FileNotFoundError(f"Markdown file not found: {picked}")
    return picked.resolve()
