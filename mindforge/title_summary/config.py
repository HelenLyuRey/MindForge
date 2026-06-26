from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from mindforge.config import get_paths, load_project_env
from mindforge.llm.client import LLMConfig, load_llm_config


@dataclass(frozen=True)
class TitleSummaryConfig:
    project_root: Path
    export_dir: Path
    intermediate_dir: Path
    llm: LLMConfig
    batch_size: int = 10
    max_input_chars: int = 12000


def load_config() -> TitleSummaryConfig:
    load_project_env()
    paths = get_paths()
    return TitleSummaryConfig(
        project_root=paths.project_root,
        export_dir=paths.export_dir,
        intermediate_dir=paths.intermediate_dir,
        llm=load_llm_config(),
        batch_size=int(os.getenv("PIPELINE_BATCH_SIZE", "10")),
        max_input_chars=int(os.getenv("PIPELINE_MAX_INPUT_CHARS", "12000")),
    )
