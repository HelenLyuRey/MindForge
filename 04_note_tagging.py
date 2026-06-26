from __future__ import annotations

import argparse
import json
import sys

from mindforge.enrichment import enrich_all_notes, preview_one_note


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Stage 4: tag and enrich exported DeepSeek notes.")
    parser.add_argument("--preview", action="store_true", help="Preview one note without writing files.")
    parser.add_argument("--path", default=None, help="Optional markdown path or filename for preview.")
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of notes to enrich.")
    parser.add_argument("--force", action="store_true", help="Rebuild notes even when the manifest signature matches.")
    parser.add_argument("--tag-count", type=int, default=3, help="Target number of taxonomy tags.")
    args = parser.parse_args()

    if args.preview:
        result = preview_one_note(args.path, tag_count=args.tag_count)
    else:
        result = enrich_all_notes(limit=args.limit, force=args.force, tag_count=args.tag_count)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
