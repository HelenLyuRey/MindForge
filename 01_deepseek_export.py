from __future__ import annotations

import argparse
import json
import logging
import sys

from mindforge_core.export import run_export


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Stage 1: export DeepSeek conversations to Markdown.")
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of conversations to export.")
    parser.add_argument("--quiet", action="store_true", help="Only print the final JSON summary.")
    args = parser.parse_args()
    if not args.quiet:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(json.dumps(run_export(limit=args.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
