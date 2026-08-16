from __future__ import annotations

import argparse
import logging

from mindforge_core.console import configure_console, print_json
from mindforge_core.export import run_export


def main() -> None:
    configure_console()

    parser = argparse.ArgumentParser(description="Stage 1: export DeepSeek conversations to Markdown.")
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of conversations to export.")
    parser.add_argument("--quiet", action="store_true", help="Only print the final JSON summary.")
    args = parser.parse_args()
    if not args.quiet:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    print_json(run_export(limit=args.limit))


if __name__ == "__main__":
    main()
