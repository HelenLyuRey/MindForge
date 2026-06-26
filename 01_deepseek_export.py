from __future__ import annotations

import argparse
import json
import sys

from mindforge.export import run_export


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Stage 1: export DeepSeek conversations to Markdown.")
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of conversations to export.")
    args = parser.parse_args()
    print(json.dumps(run_export(limit=args.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
