# Scholar — Prototype

Minimal prototype scaffold for the Scholar desktop app (Windows-first).

## Quickstart

1. Create a virtual environment and activate it (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Initialize the DB:

```powershell
python -m src.scholar.db_init
```

3. Run the prototype viewer:

```powershell
python -m src.scholar.main
```

## Features

- **PDF Rendering**: Open PDFs with PyMuPDF, render pages as images.
- **Navigation**: Previous/Next buttons, page spinbox, slider, fit-to-width toggle, continuous scroll mode, thumbnails dialog, mouse wheel paging, customizable shortcuts.
- **Annotations**: Save selected text with notes and confidence levels to SQLite DB.
- **Sidebar**: Lists all annotations for the current document.
- **AI Stub**: "Explain with AI" button (shows placeholder; needs Anthropic API key for real calls).

## Usage

- Open a PDF with the "Open PDF" button.
- Navigate pages with buttons, spinbox, slider, or shortcuts (Left/Right/Home/End).
- Toggle "Fit width" for zoom-to-fit, "Continuous" for scroll mode.
- Click "Thumbnails" for a grid of page previews.
- Select text in the middle panel, add a note, set confidence, and save.
- Annotations appear in the right sidebar.
- Click "Explain with AI" for placeholder explanation (integrate Anthropic API later).

## Database

- `scholar.db`: SQLite with full schema from bootstrap (documents, annotations, etc.).
- Tables: documents, annotations, tags, ai_outputs, etc.

## Notes

- Uses PySide6 for UI and PyMuPDF for PDF handling.
- Async AI calls ready (qasync integrated); provide Anthropic API key to enable.
- Windows-native UI; no Mac elements.
