from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ProjectPaths:
    project_root: Path = PROJECT_ROOT
    export_dir: Path = PROJECT_ROOT / "DeepSeek_Exports"
    intermediate_dir: Path = PROJECT_ROOT / "intermediate_markdowns"
    taxonomy_state_dir: Path = PROJECT_ROOT / "taxonomy_state"
    taxonomy_file: Path = PROJECT_ROOT / "taxonomy_state" / "taxonomy_v1.json"
    enriched_dir: Path = PROJECT_ROOT / "DeepSeek_Enriched"
    notebooks_backlog_dir: Path = PROJECT_ROOT / "notebooks_backlog"
    scripts_dir: Path = PROJECT_ROOT / "scripts"
    cookie_file: Path = PROJECT_ROOT / "deepseek_cookies.json"


def load_project_env(override: bool = False) -> None:
    load_dotenv(PROJECT_ROOT / ".env", override=override)


def get_paths() -> ProjectPaths:
    return ProjectPaths()


def optional_path_from_env(env_name: str) -> Path | None:
    value = os.getenv(env_name, "").strip()
    return Path(value) if value else None
