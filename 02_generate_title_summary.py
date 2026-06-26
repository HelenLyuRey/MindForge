from __future__ import annotations

import argparse
import json
import sys

from mindforge.title_summary import load_config, run_pipeline


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Stage 2: generate title and summary markdowns.")
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of notes to process.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite matching output filenames.")
    parser.add_argument("--no-resume", action="store_true", help="Ignore the checkpoint file.")
    args = parser.parse_args()
    result = run_pipeline(
        load_config(),
        limit=args.limit,
        overwrite=args.overwrite,
        resume_from_checkpoint=not args.no_resume,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
