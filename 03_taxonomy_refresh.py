from __future__ import annotations

import json
import sys

from mindforge.taxonomy import refresh_taxonomy


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    taxonomy = refresh_taxonomy()
    print(
        json.dumps(
            {
                "version": taxonomy.get("version"),
                "category_count": len(taxonomy.get("categories", [])),
                "generated_at": taxonomy.get("generated_at"),
                "language_stats": taxonomy.get("language_stats", {}),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
