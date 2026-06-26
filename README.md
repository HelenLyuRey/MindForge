# MindForge

MindForge exports DeepSeek conversations, generates note titles and summaries, applies a maintained taxonomy, and writes enriched Obsidian-ready Markdown notes.

The original notebooks are preserved in `notebooks_backlog/`. The active workflow now lives in importable Python modules under `mindforge/` with thin numbered entrypoint scripts at the project root.

## Workflow

Run stages in this order:

```bash
python 01_deepseek_export.py
python 02_generate_title_summary.py
python 04_note_tagging.py
```

If DeepSeek export access is blocked by network or IT policy, do not run `01_deepseek_export.py`. You can still run later stages against existing files in `DeepSeek_Exports/`, `intermediate_markdowns/`, and `taxonomy_state/`.

## Project Structure

```text
MindForge/
├── 01_deepseek_export.py
├── 02_generate_title_summary.py
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

Run it from the project root:

```bash
python 01_deepseek_export.py
```

Useful options:

```bash
python 01_deepseek_export.py --limit 10
python 01_deepseek_export.py --quiet
```

By default, the command prints terminal logs showing where files are written, how many chats were found, and which chats are new, updated, or already up to date. Use `--quiet` if you only want the final JSON summary.

Stage 1 exports a conversation when either:

- It is a new DeepSeek chat that has not been exported before.
- It is an existing DeepSeek chat that has new follow-up messages or other updates since the last export.

Updated chats are re-exported. If the refreshed chat now writes to a different filename, the previous exported Markdown file is removed.

### 2. Generate Titles And Summaries

`02_generate_title_summary.py` reads `DeepSeek_Exports/*.md`, generates `generated_title` and `summary`, and writes processed files into `intermediate_markdowns/`.

Run it from the project root after Stage 1:

```bash
python 02_generate_title_summary.py
```

Useful options:

```bash
python 02_generate_title_summary.py --limit 10
python 02_generate_title_summary.py --overwrite
python 02_generate_title_summary.py --no-resume
```

The normal command already processes only new or changed exports. `--overwrite` does not make Stage 2 process more chats; it only controls what happens if a note being written has the same filename as an existing intermediate Markdown file. Without `--overwrite`, Stage 2 avoids filename collisions by creating a numbered filename such as `_2`.

Stage 2 remembers which exported chats have already been turned into intermediate Markdown, so reruns only work on new or changed exports.

Stage 2 generates an intermediate Markdown when either:

- The exported DeepSeek chat has not been turned into an intermediate Markdown file before.
- The exported DeepSeek chat changed since the last intermediate Markdown was generated.

Updated exports are regenerated. If the refreshed intermediate note now writes to a different filename, the previous intermediate Markdown file is removed.

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

The final JSON summary includes `new_sources`, `updated_sources`, and `skipped_unchanged`.

### 3. Maintain Taxonomy

`taxonomy_state/taxonomy_v1.json` is the maintained taxonomy used by note tagging. Update it deliberately when categories need to change.

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

- Stage 1 exports new DeepSeek chats that have not been saved locally before.
- Stage 1 re-exports existing DeepSeek chats when they have new follow-up messages or other updates.
- Stage 1 skips existing DeepSeek chats that are already up to date locally.
- Stage 2 generates intermediate Markdown for newly exported chats.
- Stage 2 regenerates intermediate Markdown when an exported chat changed after the previous intermediate file was created.
- Stage 2 skips exported chats whose intermediate Markdown is already up to date.
- Stage 4 skips enriched notes that are already up to date with the current source note and taxonomy.

## Notes

- `deepseek_cookies.json` and `.env` may contain private credentials and should not be shared.
- The notebook backlog is intentionally retained for reference and is not part of the active Python workflow.
- Raw exports remain in `DeepSeek_Exports/`; enriched notes are written separately to `DeepSeek_Enriched/`.
