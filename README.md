# MindForge

MindForge exports DeepSeek conversations, generates note titles and summaries, applies a maintained taxonomy, and writes tagged Obsidian-ready Markdown notes.

The original notebooks are preserved in `notebooks_backlog/`. The active workflow now lives in importable Python modules under `mindforge_core/` with thin numbered entrypoint scripts at the project root.

## Note Layers

Each note uses three separate layers. They answer different questions and should not be mixed into one tag list.

| Layer | Field | Question | Values |
|---|---|---|---|
| Kind | `kind` | What kind of file is this? | `chat`, `essay` |
| Purpose | `purpose` | What was this chat for, and will I reopen it? | `think-out-loud-reflection`, `deep-learning`, `creation`, `lookup` |
| Tags | `tags` | What is this about? | Chinese taxonomy labels and subtopics, such as `自我成长` or `亲密关系` |

**Kind** is the object type. `chat` is a DeepSeek conversation saved by this pipeline. `essay` is a standalone piece of writing: a birthday letter, a handwritten journal, or a later progress digest. Essays are not a fifth chat purpose. They live beside chat notes, can reuse the same topic tags, and can link back to the chats they grew from.

**Purpose** is only for `kind: chat`. It says how the conversation was used, not what topic it covered. A note can have one or two purposes.

- `think-out-loud-reflection`: messy thinking, journaling, decisions, emotional processing. Reopen later to see how you thought.
- `deep-learning`: understand a concept, framework, or domain. Reopen later as knowledge.
- `creation`: write, rewrite, design, script, slide, or prompt. The keepable thing is the artifact.
- `lookup`: compare, recommend, plan, or ask a one-shot how-to. Rarely reopen.

**Tags** are the topic layer from `taxonomy_state/taxonomy_v1.json`. They stay in Chinese. Category labels and subtopics are equal flat tags, so one note can mix `自我成长`, `情绪疗愈`, and `分离焦虑`.

A pipeline chat note:

```yaml
kind: chat
purpose:
  - think-out-loud-reflection
tags:
  - 自我成长
  - 身份转型
  - 亲密关系
```

A handwritten birthday essay, or a later AI progress digest:

```yaml
kind: essay
tags:
  - 自我成长
  - 亲密关系
```

Essays do not get `purpose`. Purpose describes a conversation. An essay is already the written piece.

The chat pipeline produces `kind: chat` notes. Stage 3 stamps `kind: chat`, classifies `purpose` from the title and summary, and attaches topic `tags`. Essays are written in the vault, not exported from DeepSeek.

## Workflow

Run stages in this order:

```bash
python 01_deepseek_export.py
python 02_generate_title_summary.py
python 03_add_label.py
```

Or run the full setup and pipeline on Windows:

```bat
run_pipeline.bat
```

`run_pipeline.bat` creates `mindforge-env` if needed, installs dependencies, installs Playwright Chromium, then runs stages 01, 02, and 03 in sequence. If any setup step or stage fails, it stops immediately and leaves the command error visible in the terminal.

If DeepSeek export access is blocked by network or IT policy, do not run `01_deepseek_export.py`. You can still run later stages against existing files in `pipeline_outputs/01_deepseek_export/`, `pipeline_outputs/02_intermediate_markdowns/`, and `taxonomy_state/`.

## Project Structure

```text
MindForge/
├── 01_deepseek_export.py
├── 02_generate_title_summary.py
├── 03_add_label.py
├── mindforge_core/
│   ├── config.py
│   ├── llm/
│   ├── markdown/
│   ├── export/
│   ├── title_summary/
│   ├── labels/
│   └── scripts/
│       ├── pw_login.py
│       ├── pw_fetch_convos.py
│       └── pw_fetch_messages.py
├── notebooks_backlog/
│   ├── 1.deepseek_export.ipynb
│   ├── 2.generate_title_summary_pipeline.ipynb
│   ├── 3.taxonomy_refresh.ipynb
│   └── 3.note_tagging.ipynb
├── pipeline_outputs/
│   ├── 01_deepseek_export/
│   ├── 02_intermediate_markdowns/
│   └── 03_final_markdowns/
└── taxonomy_state/
```

## Stages

### 1. Export DeepSeek Conversations

`01_deepseek_export.py` exports DeepSeek chat history into `pipeline_outputs/01_deepseek_export/` and updates `pipeline_outputs/01_deepseek_export/conversations_manifest.json`.

It uses `DEEPSEEK_TOKEN` from `.env`, then tries DeepSeek API calls first and Playwright fallback scripts in `mindforge_core/scripts/` if needed.

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

`02_generate_title_summary.py` reads `pipeline_outputs/01_deepseek_export/*.md`, generates `generated_title` and `summary`, and writes processed files into `pipeline_outputs/02_intermediate_markdowns/`.

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

### 3. Add Taxonomy Labels

`03_add_label.py` reads `pipeline_outputs/02_intermediate_markdowns/*.md`, stamps `kind: chat`, assigns `purpose`, matches topic labels from `taxonomy_state/taxonomy_v1.json`, and writes Obsidian-ready Markdown into `pipeline_outputs/03_final_markdowns/`.

To also save the final notes into an Obsidian vault, set `OBSIDIAN_VAULT_PATH` in `.env`. Stage 3 writes the final Markdown files directly into that folder.

```env
OBSIDIAN_VAULT_PATH=C:\Users\you\Documents\Obsidian\MyVault
```

Run it from the project root after Stage 2:

```bash
python 03_add_label.py
```

Useful options:

```bash
python 03_add_label.py --preview
python 03_add_label.py --limit 5
python 03_add_label.py --force
python 03_add_label.py --purpose-only
```

Stage 3 writes three layers onto each chat note:

- `kind: chat` is always stamped. The pipeline does not classify essays.
- `purpose` is a separate classifier that uses the title and summary. It chooses one or two of `think-out-loud-reflection`, `deep-learning`, `creation`, and `lookup`.
- `tags` still come from the Chinese taxonomy. Category labels and subtopics are treated equally, so an Obsidian note can be tagged with a mix such as `自我成长`, `情绪疗愈`, `灾难化心理`, `分离焦虑`, and `亲密陪伴`.

`--force` rebuilds tags and purpose. `--purpose-only` rebuilds purpose and keeps existing tags. See [Note Layers](#note-layers) for the full model.

`taxonomy_state/taxonomy_v1.json` is the maintained taxonomy used by note tagging. Update it deliberately when labels or subtopics need to change.

## Setup

```bash
python -m venv mindforge-env
mindforge-env\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

The setup commands above are also included in `run_pipeline.bat`. Before running the pipeline, copy `.env-example` to `.env` and fill in the required credentials. If `.env` is missing, the BAT file creates it from `.env-example` and stops so you can edit it first.

## Incremental Behavior

- Stage 1 exports new DeepSeek chats that have not been saved locally before.
- Stage 1 re-exports existing DeepSeek chats when they have new follow-up messages or other updates.
- Stage 1 skips existing DeepSeek chats that are already up to date locally.
- Stage 2 generates intermediate Markdown for newly exported chats.
- Stage 2 regenerates intermediate Markdown when an exported chat changed after the previous intermediate file was created.
- Stage 2 skips exported chats whose intermediate Markdown is already up to date.
- Stage 3 skips final Markdown files that already have `kind`, `purpose`, and `tags`, unless `--force` or `--purpose-only` is used.
- Stage 3 fills missing `purpose` without rebuilding existing tags.
- If `OBSIDIAN_VAULT_PATH` is configured, skipped files are still synced from `pipeline_outputs/03_final_markdowns/` into the Obsidian destination.

## Notes

- `deepseek_cookies.json` and `.env` may contain private credentials and should not be shared.
- The notebook backlog is intentionally retained for reference and is not part of the active Python workflow.
- Raw exports remain in `pipeline_outputs/01_deepseek_export/`; title/summary notes are written to `pipeline_outputs/02_intermediate_markdowns/`; tagged notes are written to `pipeline_outputs/03_final_markdowns/`. If configured, tagged notes are also copied into the Obsidian vault destination.
