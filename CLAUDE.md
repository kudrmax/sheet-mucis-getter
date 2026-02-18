# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Bot

```bash
# Activate venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

Requires `.env` with `BOT_TOKEN`, `GOOGLE_DRIVE_FOLDER_ID`, `CREDENTIALS_PATH` and a valid `credentials.json` (Google Service Account).

## Architecture

Telegram bot (aiogram 3.x) for browsing and managing sheet music on Google Drive via a service account.

**Entry point:** `main.py` — creates `DriveService`, injects it + `root_folder_id` into aiogram `Dispatcher` as middleware data.

**Three layers:**

- `bot/handlers.py` — aiogram Router with FSM-based flows. Two main user flows:
  - **Download:** select folders via inline keyboard → batch download all files → send as ZIP
  - **Upload:** pick/create folder → send documents → confirm/rename filename → upload
- `bot/keyboards.py` — inline and reply keyboard builders. Constants `CHOOSE_SHEETS` / `UPLOAD_SHEETS` are used as text filters in handlers.
- `services/drive_service.py` — Google Drive API v3 wrapper with modifiedTime-based caching. Uses thread-local service instances for `download_file` (runs in `asyncio.to_thread`).

**Caching (DriveService):**
- `list_folders` / `list_files` — cached by parent folder ID, validated via lightweight `modifiedTime` API call before serving from cache.
- `download_file` — cached by file ID, invalidated when parent folder's `list_files` cache misses.
- Mutations (`create_folder`, `upload_file`) — instantly invalidate relevant cache entries.
- No TTL, no background tasks.

**FSM states** (`SheetStates`): `selecting_folders` → download flow; `choosing_upload_folder` → `entering_new_folder_name` → `waiting_for_files` → `confirming_filename` → upload flow.

## Language

Bot UI is in Russian. Code comments and variable names are in English.
