from __future__ import annotations

import argparse
import logging

from mindforge_core.console import configure_console, print_json
from mindforge_core.title_summary import load_config, run_pipeline


def main() -> None:
    configure_console()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

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
    print_json(result)


if __name__ == "__main__":
    main()
