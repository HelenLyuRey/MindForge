from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from mindforge_core.config import get_paths, load_project_env
from mindforge_core.llm.client import LLMConfig, load_llm_config


@dataclass(frozen=True)
class LabelConfig:
    project_root: Path
    intermediate_dir: Path
    final_dir: Path
    taxonomy_file: Path
    llm: LLMConfig
    max_input_chars: int = 50000
    max_tags: int = 5


def load_config() -> LabelConfig:
    load_project_env()
    paths = get_paths()
    return LabelConfig(
        project_root=paths.project_root,
        intermediate_dir=paths.intermediate_dir,
        final_dir=paths.final_dir,
        taxonomy_file=paths.taxonomy_file,
        llm=load_llm_config(),
        max_input_chars=int(os.getenv("LABEL_MAX_INPUT_CHARS", "50000")),
        max_tags=int(os.getenv("LABEL_MAX_TAGS", "5")),
    )
