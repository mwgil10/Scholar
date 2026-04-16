# Scholar UI Specification

## Purpose

This document defines the current UI surface, pane geometry, visibility rules, and high-value UI states for the Scholar desktop application.

It is meant to close the execution gap between the high-level architecture description and the actual Qt widget structure in [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py).

## Scope

This spec covers:

- top-level window layout
- primary pane geometry
- region responsibilities
- collapsed vs expanded panel behavior
- document and project switching surface changes
- annotation workspace states

It does not define color tokens in detail. Visual styling remains code-driven for now.

## Top-Level Surface

The application window is a single `QMainWindow` with:

- a top ribbon
- a horizontal body splitter

The body splitter contains three columns:

1. left library pane
2. center PDF reading area
3. right inspector pane

Current default splitter sizes in code:

- left: `280`
- center: `900`
- right: `300`

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):724

## Layout Contract

### Region A: Ribbon

The ribbon is always visible and spans the full width of the window.

Primary groups currently represented:

- library actions
- navigation
- search
- view
- annotation / explain
- session
- export
- shortcuts
- theme toggle

The ribbon is not collapsible in the current contract.

### Region B: Left Library Pane

The left pane is collapsible through the ribbon "Hide Lib" control.

Current sizing contract:

- minimum width: `240`
- default visible width: about `280`
- may collapse to width `0`

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):293
- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):724

This pane is vertically scrollable and contains two major sections:

1. `Project Space`
2. `Documents`
3. `Source Organizer`

### Region C: Center PDF Area

The center region is the primary reading surface.

It contains:

- a scroll area
- either one current page label or a continuous pages layout
- the active PDF rendering surface

This region is the only non-collapsible region in the middle of the body splitter and should remain the dominant width consumer.

### Region D: Right Inspector Pane

The right pane contains a nested vertical splitter with two stacked sections:

1. `Saved annotations`
2. `Annotation workspace`

Current sizing contract:

- minimum width: `260`
- maximum width: `520`
- default inner sizes: `[340, 420]`

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):483
- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):700

## Left Pane Specification

### Project Space Section

Controls:

- project selector dropdown
- `New` project button
- scope hint label

Behavior:

- changing the project selector updates document scope, organizer context, and annotation scope
- project selection is a global state change

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):301
- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):1863

### Documents Section

Controls:

- active record label
- search field
- sort dropdown
- status filter dropdown
- document list

Behavior:

- list content is project-sensitive when a project is selected
- clicking a document:
  - populates organizer fields
  - schedules PDF open
  - updates active reader surface

### Source Organizer Section

Controls include:

- annotation record selector
- `New Record` button
- title
- author
- year
- status
- priority
- reading type
- source
- volume / issue / pages
- DOI
- URL
- publisher
- path label
- save button

Current contract:

- organizer is hidden by default on startup
- organizer can be shown or hidden with a dedicated toggle
- metadata fields autosave on editing-finished for most inputs

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):371

## Right Pane Specification

### Saved Annotations Panel

Always conceptually above the annotation workspace.

Controls:

- section header
- hint label
- annotation search field
- annotation scope selector
- type filter
- sort selector
- tag filter
- annotation list

Annotation scope values:

- `page`
- `document`
- `project`

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):513

### Annotation Workspace Panel

This is the active creation/edit surface for one annotation draft.

Current intended responsibilities:

- choose annotation type
- edit selected text
- edit note
- assign confidence
- assign writing project
- assign tags
- inspect AI explanation
- save or update annotation

Current visibility contract:

- visible by default
- can be hidden with the workspace toggle

## Window States

### State 1: No Document Loaded

Expected surface:

- center area has no active PDF content
- active record label reads as empty / none
- annotation list shows "No document loaded."
- annotation workspace may remain visible but should not imply a valid save target
- session actions that require a document must show blocking warnings

### State 2: Document Loaded

Expected surface:

- center area shows current PDF page or continuous page list
- left organizer is populated for the current record when available
- annotation list becomes queryable
- annotation scope labels update to current page / document / project

### State 3: Project Selected, Current Document In Project

Expected surface:

- document list filtered to selected project
- organizer tied to the selected project-source record
- project-level annotation scope is meaningful
- saved annotations may show source titles when scope is `project`

### State 4: Project Selected, Current Document Not In Project

Expected surface:

- reader may still display the open document
- organizer clears or indicates no project-source record
- annotation creation should not silently attach to the wrong project-source context

### State 5: Annotation Draft New

Expected surface:

- workspace state label indicates a new draft
- selected text and note fields reflect the current draft
- save action creates a new annotation

### State 6: Annotation Editing Existing

Expected surface:

- workspace populated from a selected saved annotation
- save action performs update, not insert
- current annotation ID is retained until cleared

## Annotation Workspace State Model

Current logical draft modes visible in code:

- `idle`
- `draft_new`
- `editing_existing`

UI contract:

- `idle`: workspace indicates readiness; save should not proceed without sufficient input
- `draft_new`: selected text and/or note represent a new annotation draft
- `editing_existing`: save updates the selected annotation record

## Resize and Collapse Contract

### Body Splitter

- left pane may collapse
- center pane must remain primary
- right pane should remain visible during normal operation

### Organizer Panel

- hidden by default
- opened only when user wants metadata/record editing

### Annotation Workspace

- may be hidden to favor saved annotation browsing
- hiding the workspace must not destroy draft state unless explicitly cleared

## Interaction Rules

### Project Switching

When the project changes, the UI must:

1. update project state
2. update scope hint
3. clear or reset the annotation editor appropriately
4. refresh current project-source mapping
5. refresh the document list
6. refresh saved annotations
7. repopulate organizer if a valid current project-source exists

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):1863

### Document Click

When a document is clicked:

1. organizer is populated first
2. PDF loading is deferred with `QTimer.singleShot(0, ...)`
3. deferred load avoids crashing during list refresh in the click event

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):2582

This deferred-open behavior is part of the current stability contract and should not be removed casually.

## Implementation Guardrails

- The three-column body splitter is a structural commitment and should be treated as stable unless intentionally redesigned.
- The right inspector remains a two-zone stacked surface, not a tabbed view.
- Project space is a global context switch, not a local filter widget.
- The organizer is a metadata/edit panel, not a second browsing pane.
- The annotation workspace is a stateful editor, not a transient modal.

## Recommended Next UI Artifact

If a visual companion doc is added later, it should be a simple wireframe with:

- startup state
- document-loaded state
- organizer open state
- annotation editing state
- project switch state

