from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mindforge.config import get_paths
from mindforge.llm.client import LLMConfig, llm_call_json, load_llm_config
from mindforge.llm.preflight import provider_preflight_check
from mindforge.taxonomy.corpus import load_markdown_corpus


TARGET_LABEL_LANGUAGE = "zh"
MAX_DISCOVERY_DOCS = 60


def refresh_taxonomy(
    *,
    corpus_dir: Path | None = None,
    taxonomy_file: Path | None = None,
    llm_config: LLMConfig | None = None,
) -> dict[str, Any]:
    paths = get_paths()
    corpus_path = corpus_dir or paths.intermediate_dir
    target_file = taxonomy_file or paths.taxonomy_file
    llm = llm_config or load_llm_config()

    docs = load_markdown_corpus(corpus_path, project_root=paths.project_root)
    provider_preflight_check(config=llm)
    return build_or_refresh_taxonomy(docs, taxonomy_file=target_file, llm_config=llm)


def build_or_refresh_taxonomy(
    docs: list[dict[str, Any]],
    *,
    taxonomy_file: Path | None = None,
    llm_config: LLMConfig | None = None,
    target_label_language: str = TARGET_LABEL_LANGUAGE,
    max_discovery_docs: int = MAX_DISCOVERY_DOCS,
) -> dict[str, Any]:
    paths = get_paths()
    target_file = taxonomy_file or paths.taxonomy_file
    target_file.parent.mkdir(parents=True, exist_ok=True)

    sampled = docs[:max_discovery_docs]
    language_stats = Counter(doc["language"] for doc in docs)
    existing = json.loads(target_file.read_text(encoding="utf-8")) if target_file.exists() else None

    user_prompt = json.dumps(
        {
            "task": "Build or refresh taxonomy",
            "target_label_language": target_label_language,
            "rules": [
                "Preserve existing categories unless strongly necessary",
                "Add at most 3 new categories in one refresh",
                "Every category must include: category_id, label, description, include_examples, exclude_examples",
                "category_id must be stable snake_case ascii",
                "Include fallback categories: other, unclear",
                "Infer topics from only original_title, generated_title, and summary",
            ],
            "existing_taxonomy": existing,
            "language_stats": dict(language_stats),
            "documents": [
                {
                    "original_title": doc["original_title"],
                    "generated_title": doc["generated_title"],
                    "summary": doc["summary"],
                }
                for doc in sampled
            ],
            "output_schema": {
                "version": "string",
                "generated_at": "iso8601",
                "target_label_language": "zh|en",
                "categories": [
                    {
                        "category_id": "snake_case",
                        "label": "string",
                        "description": "string",
                        "include_examples": ["string"],
                        "exclude_examples": ["string"],
                    }
                ],
                "change_summary": {
                    "kept": ["category_id"],
                    "added": ["category_id"],
                    "deprecated": ["category_id"],
                },
            },
        },
        ensure_ascii=False,
    )

    taxonomy = llm_call_json(
        (
            "You are a taxonomy designer for conversation notes. Return strict JSON only. "
            "Keep stable categories if existing taxonomy is provided. "
            "Prefer concise labels in Simplified Chinese when target language is zh."
        ),
        user_prompt,
        config=llm_config,
        temperature=0.0,
    )
    taxonomy.setdefault("version", "v1")
    taxonomy["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    taxonomy["language_stats"] = dict(language_stats)
    target_file.write_text(json.dumps(taxonomy, ensure_ascii=False, indent=2), encoding="utf-8")
    return taxonomy
