import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mindforge_core.labels.pipeline import run_pipeline


class LabelPipelineProgressLoggingTests(unittest.TestCase):
    def test_run_pipeline_logs_progress_for_each_processed_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir)
            intermediate_dir = project_root / "intermediate"
            final_dir = project_root / "final"
            intermediate_dir.mkdir(parents=True, exist_ok=True)
            final_dir.mkdir(parents=True, exist_ok=True)

            note_path = intermediate_dir / "sample.md"
            note_path.write_text("---\ntitle: Sample\n---\n\nbody\n", encoding="utf-8")

            cfg = SimpleNamespace(
                project_root=project_root,
                intermediate_dir=intermediate_dir,
                final_dir=final_dir,
                llm=SimpleNamespace(),
                obsidian_vault_path=None,
                max_tags=3,
                max_input_chars=1000,
                taxonomy_file=project_root / "taxonomy.json",
            )

            taxonomy = {"categories": [], "flat_tags": ["tag1"]}
            with patch("mindforge_core.labels.pipeline.provider_preflight_check"), patch(
                "mindforge_core.labels.pipeline.load_taxonomy_tags", return_value=taxonomy
            ), patch("mindforge_core.labels.pipeline.label_record", return_value={"tags": ["tag1"], "confidence": 1.0, "reason": "ok"}), patch(
                "mindforge_core.labels.pipeline.classify_purpose",
                return_value={"purpose": ["lookup"], "purpose_confidence": 1.0, "purpose_reason": "ok"},
            ), patch(
                "mindforge_core.labels.pipeline.publish_record", return_value={"output_path": final_dir / "sample.md", "obsidian_path": None}
            ):
                with self.assertLogs("mindforge_core.labels.pipeline", level="INFO") as captured:
                    run_pipeline(cfg, force=True)

            self.assertTrue(any("Processed" in message and "sample.md" in message for message in captured.output))


if __name__ == "__main__":
    unittest.main()
