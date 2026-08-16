import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mindforge_core.title_summary.pipeline import run_pipeline


class TitleSummaryPipelineProgressLoggingTests(unittest.TestCase):
    def test_run_pipeline_logs_progress_for_each_processed_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg = SimpleNamespace(
                intermediate_dir=Path(tmp_dir),
                llm=SimpleNamespace(),
            )
        rows = [
            {
                "source_file": "note-1.md",
                "source_hash": "hash-1",
                "source_modified_at": "2026-06-28T00:00:00+00:00",
                "body": "body",
                "original_title": "Original",
            }
        ]

        with patch("mindforge_core.title_summary.pipeline.provider_preflight_check"), patch(
            "mindforge_core.title_summary.pipeline.ingest_exports", return_value=rows
        ), patch("mindforge_core.title_summary.pipeline.transform_record", return_value={**rows[0], "generated_title": "Title", "summary": "Summary", "error": ""}), patch(
            "mindforge_core.title_summary.pipeline.validate_records"
        ), patch(
            "mindforge_core.title_summary.pipeline.publish_rows", return_value=[{"source_file": "note-1.md", "output_file": "out.md"}]
        ), patch("mindforge_core.title_summary.pipeline.append_jsonl") as append_jsonl_mock:
            with self.assertLogs("mindforge_core.title_summary.pipeline", level="INFO") as captured:
                run_pipeline(cfg, resume_from_checkpoint=False)

        self.assertTrue(any("Processed" in message and "note-1.md" in message for message in captured.output))
        append_jsonl_mock.assert_called()


if __name__ == "__main__":
    unittest.main()
