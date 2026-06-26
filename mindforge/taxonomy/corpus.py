from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mindforge.config import PROJECT_ROOT
from mindforge.hashing import stable_hash
from mindforge.markdown.frontmatter import extract_frontmatter_and_body
from mindforge.markdown.language import detect_language_simple


def load_markdown_corpus(corpus_dir: Path, *, project_root: Path = PROJECT_ROOT) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in sorted(corpus_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        frontmatter, _ = extract_frontmatter_and_body(raw)
        original_title = frontmatter.get("original_title", path.stem).strip()
        generated_title = frontmatter.get("generated_title", original_title).strip()
        summary = frontmatter.get("summary", "").strip()
        signature = json.dumps(
            {
                "original_title": original_title,
                "generated_title": generated_title,
                "summary": summary,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

        docs.append(
            {
                "path": str(path.relative_to(project_root)),
                "filename": path.name,
                "original_title": original_title,
                "generated_title": generated_title,
                "summary": summary,
                "language": detect_language_simple(" ".join([original_title, generated_title, summary])),
                "content_hash": stable_hash(signature),
            }
        )
    return docs
