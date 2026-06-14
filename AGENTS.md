# AGENTS.md

## Cursor Cloud specific instructions

This repo is a single Flask app: an **AI Children's Picture Book Generator** (`app.py` + `*_service.py`). There is no database, frontend build step, or compiled assets. See `README.md` for the full feature/flow description and `curl` examples.

### Services

| Service | Command | Port | Notes |
|---|---|---|---|
| Flask web app | `source .venv/bin/activate && python app.py` | 5000 | Binds `0.0.0.0:5000`, `debug=True` (hot reload on file save). Serves both the HTML UI (`/`) and JSON API (`/api/picture-books`). `GET /health` returns `{"status":"ok"}`. |

The update script provisions a `.venv` and installs `requirements.txt`. Always run the app from that venv.

### What runs without secrets vs. what needs them

- **Local / no secrets** (deterministic): outline generation (`outline_service.py`), TXT/.docx parsing (`document_service.py`), and PDF export (`pdf_export_service.py`, uses reportlab + the built-in `STSong-Light` CJK font). The PDF exporter renders a cream placeholder box for any page with no image, so a real multi-page PDF can be produced end-to-end without calling any external API.
- **Needs secrets / network** (external SaaS, no local mock exists):
  - `NANO_BANANA_API_KEY` — required for image generation. The full `/api/picture-books` flow (UI "生成" button included) calls `api.grsai.com` for the character sheet and every page image, so it fails at the image step without a valid key (returns HTTP 400 with `图片生成失败：apikey error`). Outbound network to the API works from the VM; only the key is missing.
  - `MINERU_API_KEY` — required to parse uploaded **PDF / .doc** files (and `.docx` when the key is set). Without it, only TXT and `.docx` uploads parse locally.

### Gotchas

- `python3 -m venv` needs the `python3.12-venv` system package; the update script does not install system packages, so if venv creation fails run `sudo apt-get install -y python3.12-venv` first.
- `.env`, `.venv/`, and `storage/` are gitignored. Copy `.env.example` to `.env` and fill in keys before running the full image-generation flow. Generated PDFs/images land in `storage/outputs/`.
- To exercise the local core pipeline directly (bypassing the image API), import `PictureBookOutlineService` and `PictureBookPdfExporter` from the repo root with `PYTHONPATH=/workspace`.
- There is no lint config (no ruff/flake8 config committed) and no automated test suite in the repo.
