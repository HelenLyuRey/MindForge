from __future__ import annotations

import argparse
import json
import sys

from mindforge_core.labels import load_config, run_pipeline


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Stage 3: add kind, purpose, and taxonomy tags to chat notes."
    )
    parser.add_argument("--preview", action="store_true", help="Preview matching without writing files.")
    parser.add_argument("--path", default=None, help="Optional intermediate markdown path or filename.")
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of notes to tag.")
    parser.add_argument("--force", action="store_true", help="Rebuild tags and purpose when output files already exist.")
    parser.add_argument(
        "--purpose-only",
        action="store_true",
        help="Rebuild purpose only. Keep existing tags when a final note already exists.",
    )
    args = parser.parse_args()

    result = run_pipeline(
        load_config(),
        path=args.path,
        limit=args.limit,
        force=args.force,
        preview=args.preview,
        purpose_only=args.purpose_only,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
