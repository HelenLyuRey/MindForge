# MindForge

A notebook-based pipeline that saves your DeepSeek AI conversations, builds a reusable taxonomy, and produces enriched Obsidian-ready notes with better titles and tags.

## What It Does

- **Stage 1 - Export**: Downloads every conversation you've had on [DeepSeek](https://chat.deepseek.com) and converts it into Markdown.
- **Stage 2 - Taxonomy**: Builds or refreshes a taxonomy JSON file that acts as the labeling source of truth.
- **Stage 3 - Enrichment**: Reads each exported note, applies the best-fit taxonomy tags, generates a better title, and writes enriched copies to a separate output location.
- **Incremental by default**: Each stage can be re-run without blindly reprocessing unchanged data.

## Project Structure

```
MindForge/
├── deepseek_export.ipynb   ← Stage 1: export DeepSeek chats to Markdown
├── taxonomy_refresh.ipynb ← Stage 2: build/refresh taxonomy JSON
├── taxonomy_apply.ipynb   ← Stage 3: tag notes and rewrite titles
├── scripts/                ← Helper scripts for browser automation
│   ├── pw_login.py
│   ├── pw_fetch_convos.py
│   └── pw_fetch_messages.py
├── DeepSeek_Exports/       ← Your exported conversations land here
│   ├── 2026-04-20_a3f2d1c9.md
│   ├── 2026-04-21_b7e4f2a0.md
│   └── conversations_manifest.json
├── DeepSeek_Enriched/      ← Stage 3 writes enriched Markdown copies here
│   └── enrichment_manifest.json
├── taxonomy_state/         ← Stage 2 taxonomy state lives here
│   └── taxonomy_v1.json
├── requirements.txt
└── .gitignore
```

## Prerequisites

- Python 3.9 or later
- A DeepSeek account (Google login supported)
- Internet access to DeepSeek (not blocked by firewall/VPN)

## Getting Started

### 1. Clone and set up

```bash
git clone <your-repo-url>
cd MindForge

python -m venv mindforge-env

# Windows
mindforge-env\Scripts\activate

# macOS/Linux
source mindforge-env/bin/activate

pip install -r requirements.txt
playwright install chromium
```

### 2. Run the notebooks in order

Open the notebooks in VS Code or Jupyter and run them in this order:

#### Stage 1 - Export conversations

Open `deepseek_export.ipynb` and run the cells in order:

| Cells | What happens |
|-------|--------------|
| 1–2 | Installs packages and imports libraries |
| 3 | Sets up paths and configuration |
| 4 | **Opens a browser window** — log in with your Google account. Cookies are saved so you only do this once. |
| 5 | Fetches the list of all your conversations |
| 6 | Defines how to read individual conversations |
| 7 | Defines how to create Markdown files |
| 8 | **Runs the full export** — downloads and saves all conversations |
| 9 | Shows a summary of what was exported |

#### Stage 2 - Build taxonomy

Open `taxonomy_refresh.ipynb`:

| Cells | What happens |
|-------|--------------|
| 1-2 | Explains the taxonomy workflow and model choice |
| 3-4 | Imports libraries and sets taxonomy configuration |
| 5-8 | Defines corpus loading, utility helpers, and LLM classification functions |
| 9 | Builds or refreshes `taxonomy_state/taxonomy_v1.json` |
| 10 | Lets you test classification on one exported Markdown file |

#### Stage 3 - Tag notes from the predefined taxonomy and improve titles

Open `taxonomy_apply.ipynb`:

| Cells | What happens |
|-------|--------------|
| 1-2 | Explains the enrichment workflow and output locations |
| 3-7 | Imports libraries, loads configuration, and defines enrichment helpers |
| 8 | Previews one note without writing anything |
| 9 | Runs the full enrichment pipeline and writes enriched copies |
| 10 | Notes the rerun behavior and prerequisites |

### 3. Output locations

Stage 1 writes the raw source notes into `DeepSeek_Exports/`.

Stage 3 writes enriched copies into `DeepSeek_Enriched/` and never overwrites the raw source notes. If you set `ENRICHED_OBSIDIAN_VAULT_PATH`, the same enriched files are also copied into that separate Obsidian vault or subfolder.

### 4. Import into Obsidian

1. Open Obsidian
2. Open (or create) a vault for raw exports, or a separate vault for enriched notes
3. Copy either `DeepSeek_Exports` or `DeepSeek_Enriched` into the vault folder depending on which stage you want to browse
4. Your conversations will appear as notes with metadata, and enriched notes will also include taxonomy tags and refined titles

### 5. Incremental updates

Re-run whichever stage you need:

- Stage 1 reads `DeepSeek_Exports/conversations_manifest.json` and skips already exported conversations.
- Stage 2 refreshes the taxonomy JSON while trying to keep categories stable.
- Stage 3 reads `DeepSeek_Enriched/enrichment_manifest.json` and skips notes whose source content and taxonomy have not changed.

## How It Works

1. **Login and fetch**: Stage 1 opens a browser for login if needed, then uses DeepSeek's internal API to fetch conversation lists and message history.
2. **Convert**: Stage 1 writes each conversation as Markdown with YAML frontmatter.
3. **Learn labels**: Stage 2 samples the exported notes and persists a taxonomy JSON as the source of truth for labels.
4. **Enrich**: Stage 3 reads each exported note, applies a few best-fit taxonomy tags, rewrites the title, and writes the enriched copy to a separate destination.
5. **Track**: Manifest files keep each stage incremental.

## Notes

- `deepseek_cookies.json` contains your login session — it's gitignored and should never be shared.
- The AI's "deep think" reasoning steps are filtered out; only the final replies are saved.
- Image attachments are skipped.
- If any conversations fail to export, details are logged to `DeepSeek_Exports/failed_exports.log`.
- Stage 3 depends on `taxonomy_state/taxonomy_v1.json`, so run the taxonomy notebook before the enrichment notebook.
- Set `ENRICHED_OBSIDIAN_VAULT_PATH` in your `.env` if you want enriched notes copied into a separate Obsidian vault automatically.
