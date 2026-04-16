# Scholar Stack and Architecture

## Purpose

This document describes the current technical stack and application architecture of the `Scholar` project so it can be used as a build-spec reference.

It reflects the repository state at the time this file was created, not an idealized future-state design.

## Project Summary

`Scholar` is a Windows-first desktop research-reading application for working with PDFs, annotations, reading sessions, project spaces, writing projects, AI-assisted explanation, and markdown exports.

At a high level, the app:

- Opens and renders PDF documents
- Stores document and annotation data in SQLite
- Organizes documents into project spaces
- Links annotations to writing projects
- Generates reading-summary and bibliography-style exports
- Optionally calls Anthropic for concise passage explanations

## Stack

### Language

- Python 3.x

### Application Type

- Desktop application
- Monolithic local app
- Windows-first UI

### UI Framework

- PySide6

Used for:

- Main window and layout management
- Ribbon-style controls
- Document library UI
- Annotation editor UI
- Saved annotation lists
- Dialogs, menus, and interaction controls

### PDF Engine

- PyMuPDF (`fitz`)

Used for:

- Opening PDFs
- Rendering pages into images
- Reading page text and text geometry for selection/annotation workflows

### Local Database

- SQLite

Used for:

- Documents and source metadata
- Project spaces and project-source membership
- Reading sessions
- Annotations
- Tags
- Writing projects
- AI outputs
- Reading events
- Progressive summaries

### Async / Event Loop Integration

- `qasync`

Used to support async AI calls from a Qt desktop app.

### AI Integration

- Anthropic Python SDK

Current use:

- Async explanation of selected passages
- Model configured in code: `claude-sonnet-4-6`

### Environment Loading

- `python-dotenv`

Used for:

- Loading `.env`
- Reading `ANTHROPIC_API_KEY`

## Dependencies

Current declared dependencies in [requirements.txt](c:\Users\mwgil\Desktop\Scholar\requirements.txt):

- `PySide6>=6.5.0`
- `PyMuPDF>=1.22.0`
- `qasync>=0.25.0`
- `anthropic>=0.90.0`
- `python-dotenv>=1.0.0`

## Runtime Model

The app is primarily a local desktop program with a single-process architecture.

### Runtime Characteristics

- Local-first
- SQLite-backed
- File-system based PDF access
- No web server
- No API backend owned by this repo
- Optional outbound AI call to Anthropic

### Entry Points

- Database initialization: `python -m src.scholar.db_init`
- Main app: `python -m src.scholar.main`

## High-Level Architecture

The project is currently organized as a small monolith with a few major modules.

### Module Map

#### [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py)

Primary application module and main UI shell.

Responsibilities:

- Bootstraps the app
- Initializes the database
- Builds the full Qt interface
- Manages PDF loading and rendering
- Handles navigation and search
- Handles text selection and annotation creation/editing
- Handles project-space switching
- Handles reading sessions
- Invokes export workflows
- Invokes AI explanation workflows

This is the dominant orchestration layer in the application.

#### [src/scholar/db_init.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\db_init.py)

Database bootstrap and migration layer.

Responsibilities:

- Creates schema from `schema.sql`
- Adds incremental schema changes for newer features
- Seeds default/system data
- Migrates legacy document relationships into project-source structures
- Repairs default project assignment state

This functions as both schema installer and migration utility.

#### [src/scholar/export.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\export.py)

Export generation layer.

Responsibilities:

- Reading summary export
- Annotated bibliography export
- Writing project export
- Citation-line formatting
- Markdown content generation
- Export filename generation

Output format is currently markdown files.

#### [src/scholar/ai.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\ai.py)

AI service integration layer.

Responsibilities:

- Builds prompt context from selected passage data
- Calls Anthropic asynchronously
- Returns a concise explanation payload

#### [schema.sql](c:\Users\mwgil\Desktop\Scholar\schema.sql)

Base relational schema definition.

Responsibilities:

- Defines core tables
- Defines indexes
- Captures the canonical storage model for application data

## Architectural Style

The application is best described as:

- Monolithic desktop application
- Layered by responsibility, but not heavily separated
- UI-driven orchestration
- Local persistence first
- Service integration at the edge

The current codebase is not split into distinct packages such as `ui`, `services`, `repositories`, and `domain`. Instead, `main.py` carries a large share of controller/orchestration logic.

## Data Architecture

### Core Storage Pattern

The app stores state in a local SQLite database file:

- primary DB path at runtime: `src/scholar.db`

### Main Domain Areas

#### 1. Documents and Sources

There are two related storage concepts:

- `documents`
- `sources`

This suggests the app has evolved from a simpler document-only model toward a more normalized source model.

#### 2. Project Spaces

Project-space organization is handled through:

- `review_projects`
- `project_sources`

Meaning:

- a project space groups sources/documents
- a single source can be represented inside project context
- project-specific display metadata can differ from raw document metadata

#### 3. Reading Sessions

Reading-session tracking is handled through:

- `reading_sessions`

Used for:

- session intention
- starting page
- linking work to a project/source context

#### 4. Annotations

Annotation storage is handled through:

- `annotations`
- `annotation_tags`
- `annotation_links`

Annotation records include:

- selected text
- note content
- confidence
- annotation type
- page number
- project/source relationship
- session relationship

#### 5. Writing Projects

Composition-oriented grouping is handled through:

- `writing_projects`
- `annotation_writing_projects`

This allows annotations to be collected into writing outputs independent of the project-space grouping.

#### 6. AI and Summaries

AI- and synthesis-related storage includes:

- `ai_outputs`
- `progressive_summaries`

These support:

- saved AI explanations
- rolling summaries of reading progress

#### 7. Activity and Review

Additional tracking structures include:

- `reading_events`
- `review_history`
- `contradictions`
- `concept_nodes`
- `concept_edges`

This indicates planned or partial support for deeper knowledge-management workflows.

## Main Interaction Flow

### PDF Reading Flow

1. User opens a PDF from disk
2. App loads or creates a document/source record
3. App renders PDF pages with PyMuPDF
4. User navigates pages and searches text
5. User selects passage text
6. User saves annotation data into SQLite

### Project-Space Flow

1. User selects a project space
2. App refreshes current project-source context
3. Library view filters to project-relevant records
4. Annotation and organizer views refresh against that context

### Reading Session Flow

1. User starts a new session
2. App records `reading_intention`, source context, and starting page
3. Subsequent annotation/AI context can use the active session

### Writing Project Flow

1. User creates or selects a writing project
2. User links annotations to that writing project
3. Export module composes a markdown output from grouped annotations

### AI Explanation Flow

1. User selects an annotation for explanation
2. `main.py` assembles context
3. `ai.py` calls Anthropic asynchronously
4. Result is stored in `ai_outputs`
5. UI displays explanation state/result

### Export Flow

1. User chooses an export type
2. `main.py` routes to `export.py`
3. `export.py` queries SQLite and composes markdown
4. User saves the resulting file locally

## UI Architecture

The UI is centered around a `QMainWindow` in `main.py`.

### Major UI Regions

- Ribbon / top controls
- Left library / project-space / organizer pane
- Center PDF viewing area
- Right annotation and saved-annotation panels

### Main UI Responsibilities in `main.py`

- State management for current document/page/project/session
- Widget creation and styling
- Signal wiring
- Data loading and refresh behavior
- Annotation and PDF interaction behavior

## File and Directory Structure

Current relevant structure:

```text
Scholar/
  README.md
  requirements.txt
  schema.sql
  STACK_ARCHITECTURE.md
  src/
    scholar.db
    reading-summary-*.md        # generated exports, usually ignored
    runtime-errors.log          # runtime log, usually ignored
    scholar/
      __init__.py
      ai.py
      ai_stub.py
      db_init.py
      export.py
      main.py
```

## Configuration and Secrets

### Environment Variables

Current known variable:

- `ANTHROPIC_API_KEY`

### `.env`

- Loaded automatically from the repo root through `load_dotenv()`
- Ignored by git

## Build and Run Specs

### Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.scholar.db_init
python -m src.scholar.main
```

### Platform Assumption

- Windows-first development workflow
- PowerShell-oriented setup

## Current Strengths of the Build

- Simple local runtime model
- No deployment complexity for core app usage
- Rich desktop interaction model
- Real persistence layer already in place
- Export pipeline already implemented
- Project-space and writing-project concepts already represented in storage and UI

## Current Architectural Constraints

- `main.py` is very large and carries many responsibilities
- UI, persistence logic, and orchestration are tightly coupled
- There is not yet a clean service/repository/domain separation
- Schema evolution is partly split between `schema.sql` and incremental migration logic in `db_init.py`
- The app is desktop-local and not yet shaped for multi-user or server-backed deployment

## Recommended Build Classification

If you need to describe this project in one line for planning or spec review:

> `Scholar` is a Python desktop research-reader application built with PySide6, PyMuPDF, and SQLite, with local project-space organization, annotation workflows, writing-project exports, and optional Anthropic-powered explanation features.

## Recommended Future Architecture Labels

If you later want to formalize this into cleaner engineering specs, the natural target labels would be:

- Presentation layer: Qt desktop UI
- Application layer: reading, annotation, export, and project workflows
- Data layer: SQLite schema plus migration utilities
- Integration layer: Anthropic API

## Spec Snapshot

### Frontend / Client

- PySide6 desktop UI

### Application Runtime

- Python local process

### Persistence

- SQLite

### Document Processing

- PyMuPDF

### Async Integration

- qasync

### AI Provider

- Anthropic

### Export Format

- Markdown

### Primary Architecture

- Monolithic local desktop app

