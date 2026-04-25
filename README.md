# MindForge

A tool that saves all your DeepSeek AI conversations into neatly organized files you can keep forever — and browse in [Obsidian](https://obsidian.md), a popular note-taking app.

## What It Does

- **Backs up your chats**: Downloads every conversation you've had on [DeepSeek](https://chat.deepseek.com) — questions, answers, code snippets, everything.
- **Creates readable files**: Each conversation becomes its own Markdown file, named by date for easy sorting.
- **Ready for Obsidian**: Files include metadata (title, date, link) so they show up beautifully in your Obsidian vault.
- **Only grabs new stuff**: Run it again later and it'll skip conversations you've already saved — no duplicates.

## Project Structure

```
MindForge/
├── deepseek_export.ipynb   ← Main notebook (run this)
├── scripts/                ← Helper scripts for browser automation
│   ├── pw_login.py
│   ├── pw_fetch_convos.py
│   └── pw_fetch_messages.py
├── DeepSeek_Exports/       ← Your exported conversations land here
│   ├── 2026-04-20_a3f2d1c9.md
│   ├── 2026-04-21_b7e4f2a0.md
│   └── conversations_manifest.json
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

### 2. Run the notebook

Open `deepseek_export.ipynb` in VS Code or Jupyter and run the cells in order:

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

### 3. Import into Obsidian

1. Open Obsidian
2. Open (or create) a vault
3. Copy the `DeepSeek_Exports` folder into your vault folder
4. Your conversations will appear as notes with metadata

### 4. Incremental updates

Just re-run the notebook. It reads the manifest file and only exports conversations that are new since the last run.

## How It Works

1. **Login**: A browser opens for you to log in to DeepSeek via Google. Session cookies are saved locally so future runs are automatic.
2. **Fetch**: The tool calls DeepSeek's internal API to get your conversation list and message history. If the API doesn't cooperate, it falls back to reading the web page directly.
3. **Convert**: Each conversation is formatted into a Markdown file with YAML frontmatter (metadata that Obsidian understands).
4. **Track**: A manifest file keeps track of what's been exported to support incremental updates.

## Notes

- `deepseek_cookies.json` contains your login session — it's gitignored and should never be shared.
- The AI's "deep think" reasoning steps are filtered out; only the final replies are saved.
- Image attachments are skipped.
- If any conversations fail to export, details are logged to `DeepSeek_Exports/failed_exports.log`.
