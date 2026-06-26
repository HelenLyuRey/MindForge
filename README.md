# MindForge

MindForge exports DeepSeek conversations, generates note titles and summaries, builds a taxonomy, and writes enriched Obsidian-ready Markdown notes.

The original notebooks are preserved in `notebooks_backlog/`. The active workflow now lives in importable Python modules under `mindforge/` with thin numbered entrypoint scripts at the project root.

## Workflow

Run stages in this order:

```bash
python 01_deepseek_export.py
python 02_generate_title_summary.py
python 03_taxonomy_refresh.py
python 04_note_tagging.py
```

If DeepSeek export access is blocked by network or IT policy, do not run `01_deepseek_export.py`. You can still run later stages against existing files in `DeepSeek_Exports/`, `intermediate_markdowns/`, and `taxonomy_state/`.

## Project Structure

```text
MindForge/
├── 01_deepseek_export.py
├── 02_generate_title_summary.py
├── 03_taxonomy_refresh.py
├── 04_note_tagging.py
├── mindforge/
│   ├── config.py
│   ├── llm/
│   ├── markdown/
│   ├── export/
│   ├── title_summary/
│   ├── taxonomy/
│   └── enrichment/
├── notebooks_backlog/
│   ├── 1.deepseek_export.ipynb
│   ├── 2.generate_title_summary_pipeline.ipynb
│   ├── 3.taxonomy_refresh.ipynb
│   └── 3.note_tagging.ipynb
├── scripts/
│   ├── pw_login.py
│   ├── pw_fetch_convos.py
│   └── pw_fetch_messages.py
├── DeepSeek_Exports/
├── intermediate_markdowns/
├── taxonomy_state/
└── DeepSeek_Enriched/
```

## Stages

### 1. Export DeepSeek Conversations

`01_deepseek_export.py` exports DeepSeek chat history into `DeepSeek_Exports/` and updates `DeepSeek_Exports/conversations_manifest.json`.

It uses `DEEPSEEK_TOKEN` from `.env`, then tries DeepSeek API calls first and Playwright fallback scripts in `scripts/` if needed.

### 2. Generate Titles And Summaries

`02_generate_title_summary.py` reads `DeepSeek_Exports/*.md`, generates `generated_title` and `summary`, and writes processed files into `intermediate_markdowns/`.

This stage uses Kimi by default:

```env
LLM_PROVIDER=kimi
KIMI_API_KEY=...
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=kimi-k2.6
```

Kimi calls are implemented through the OpenAI-compatible chat completions API with thinking disabled, matching the Moonshot sample behavior.

The local free Ollama path is still kept. To switch back:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
```

It keeps a JSONL checkpoint at `intermediate_markdowns/_pipeline_results.jsonl` so reruns can skip completed source files.

### 3. Refresh Taxonomy

`03_taxonomy_refresh.py` reads the generated title, original title, and summary from `intermediate_markdowns/*.md`, then writes `taxonomy_state/taxonomy_v1.json`.

The taxonomy stage uses the same shared LLM provider settings. Kimi is the default:

```env
LLM_PROVIDER=kimi
KIMI_API_KEY=...
KIMI_MODEL=kimi-k2.6
```

You can still use the generic OpenAI-compatible provider if needed:

```env
LLM_PROVIDER=openai_compatible
OPENAI_BASE_URL=...
OPENAI_API_KEY=...
OPENAI_MODEL=...
```

Or switch back to local Ollama with `LLM_PROVIDER=ollama`.

### 4. Tag And Enrich Notes

`04_note_tagging.py` reads original exports from `DeepSeek_Exports/`, applies categories from `taxonomy_state/taxonomy_v1.json`, generates refined titles, and writes enriched copies into `DeepSeek_Enriched/`.

Useful options:

```bash
python 04_note_tagging.py --preview
python 04_note_tagging.py --limit 5
python 04_note_tagging.py --force
```

If `ENRICHED_OBSIDIAN_VAULT_PATH` is set in `.env`, enriched files are also copied into that vault under `ENRICHED_OBSIDIAN_SUBFOLDER` or `DeepSeek Tagged` by default.

## Setup

```bash
python -m venv mindforge-env
mindforge-env\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## Incremental Behavior

- Stage 1 skips conversations already listed in `DeepSeek_Exports/conversations_manifest.json`.
- Stage 2 resumes from `intermediate_markdowns/_pipeline_results.jsonl`.
- Stage 4 skips notes whose source content hash and taxonomy hash match `DeepSeek_Enriched/enrichment_manifest.json`.

## Notes

- `deepseek_cookies.json` and `.env` may contain private credentials and should not be shared.
- The notebook backlog is intentionally retained for reference and is not part of the active Python workflow.
- Raw exports remain in `DeepSeek_Exports/`; enriched notes are written separately to `DeepSeek_Enriched/`.
