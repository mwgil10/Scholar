# Annotation Interaction and Rendering Specification

## Purpose

This document defines the current annotation capture and highlight-rendering contract for Scholar.

It exists because annotation selection over rendered PDF imagery is the highest-risk interaction surface in the application.

## Problem Statement

Scholar renders PDF pages as images in Qt, but users annotate text, not pixels.

The application therefore needs a stable mapping between:

- PDF text geometry from PyMuPDF
- rendered pixmap coordinates
- displayed widget coordinates
- saved annotation geometry in SQLite

## Current Implementation Shape

Current implementation is widget-based, not `QGraphicsScene`-based.

Observed architecture:

- PDF page content is rendered into labels inside a scroll area
- selection events are handled through `SelectableLabel`
- page-specific annotation markers and highlights are tracked in `main.py`
- saved geometry is written into `annotations.position_json`

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):18
- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):4105

## Coordinate Spaces

The system uses four conceptual coordinate spaces.

### 1. PDF Space

Source of truth from PyMuPDF page geometry.

Properties:

- page-relative
- float coordinates
- derived from page text bounds and page rect

### 2. Relative Page Space

Normalized page-relative geometry saved to the database.

Current representation in `position_json` includes:

- `x`
- `y`
- `width`
- `height`
- `char_start`
- `char_end`
- `page`
- `regions`
- `rects`

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):4146

This normalized representation is the persistence contract because it is resilient to zoom changes and viewport size changes.

### 3. Rendered Pixmap Space

The pixel dimensions of the rendered page image currently in memory.

Used for:

- drawing overlays
- hit testing against the displayed page

### 4. Display Widget Space

The actual Qt label/widget coordinates after fit-width, zoom, and layout constraints are applied.

Used for:

- mouse press, move, and release events
- translating pointer events back into page-relative selection positions

## Selection Model

### Entry Point

Selection begins on mouse press inside `SelectableLabel`.

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):24

### Selection Lifecycle

1. mouse press begins selection
2. mouse move updates the active selection
3. mouse release finalizes selection
4. current drag may be combined with committed regions
5. annotation save serializes the resulting regions

### Multi-Region Contract

The current implementation supports multi-region selection through:

- `selection_regions`
- a current active drag region

When saving:

- all committed regions are included
- current drag region is included if active
- each region may carry its own normalized rectangle

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):4118

## Annotation Types and Input Requirements

Current annotation types:

- `quote`
- `paraphrase`
- `interpretation`
- `synthesis`

Current behavioral contract:

- `quote` requires selected text from the PDF
- `paraphrase`, `interpretation`, and `synthesis` require user note content
- some types may require both selection grounding and note content depending on current validation rules

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):4100

## Persistence Contract

### Table

- `annotations`

### Key Persisted Fields

- `document_id`
- `project_source_id`
- `session_id`
- `page_number`
- `position_json`
- `annotation_type`
- `selected_text`
- `note_content`
- `confidence_level`

### `position_json` Contract

`position_json` must be valid JSON containing enough data to re-render the highlight approximately without needing to rerun text extraction.

Required top-level keys in the current contract:

- `page`
- `char_start`
- `char_end`
- `regions`

Preferred geometry keys:

- `x`
- `y`
- `width`
- `height`
- `rects`

### Example Shape

```json
{
  "x": 0.14,
  "y": 0.28,
  "width": 0.33,
  "height": 0.04,
  "char_start": 210,
  "char_end": 284,
  "page": 5,
  "regions": [
    {
      "char_start": 210,
      "char_end": 240,
      "x": 0.14,
      "y": 0.28,
      "width": 0.18,
      "height": 0.02
    }
  ],
  "rects": [
    {
      "x": 0.14,
      "y": 0.28,
      "width": 0.18,
      "height": 0.02
    }
  ]
}
```

## Rendering Contract

### Saved Highlight Rendering

Saved highlights are rendered from normalized geometry, not recomputed from live selection state.

Required behavior:

- when an annotation is saved or reopened, its saved geometry must be reusable for drawing
- when zoom changes, highlights must scale with the rendered page
- when fit-width mode changes, highlights must still align with the page image

### Marker Rendering

The page surface may also expose annotation markers separate from highlight fills.

Required behavior:

- markers must be page-specific
- clicking a marker should route to the corresponding annotation
- marker hit testing must happen before starting a new text selection

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):24

## Transformation Contract

The transformation pipeline must remain explicit:

1. extract PDF character geometry
2. derive bounds in PDF page coordinates
3. normalize bounds relative to page rect
4. save normalized geometry
5. convert normalized geometry into current widget-space rectangles during redraw

This contract is the core guardrail against highlight drift.

## Edit vs New Annotation Behavior

### New Annotation

- uses current live selection and note state
- creates new `annotation_id`
- persists all geometry, tags, and optional writing-project relationship

### Edit Existing Annotation

- if no new live selection exists, the existing saved geometry may be retained
- if a new selection exists, saved geometry is replaced

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):4107

## Redraw Triggers

Highlights and markers must redraw when:

- current page changes
- document changes
- annotation is saved
- annotation list selection changes in a way that affects focus
- zoom changes
- fit-width mode changes
- continuous mode changes if page widgets are rebuilt

## Known Architectural Constraint

The app currently implements this interaction model inside `main.py`.

That is acceptable for the prototype, but the stable abstraction boundary should eventually become:

- selection engine
- geometry serializer
- overlay renderer
- annotation persistence service

## Guardrails for Future Refactoring

- Do not switch to a new overlay strategy without preserving normalized geometry in the database.
- Do not make widget-space rectangles the persistence format.
- Do not tie highlight rendering to a single zoom level.
- Do not assume one annotation equals one rectangle; multi-region support is already part of the contract.

## Recommended Future Refactor Units

When the code is split, the natural components are:

- `selection.py`
- `geometry.py`
- `overlays.py`
- `annotation_service.py`

