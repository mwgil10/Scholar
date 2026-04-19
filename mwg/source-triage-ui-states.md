# source-triage-ui-states.md

## Engram, Source Triage UI State Machine

**Status:** Normative for frontend implementation.  
**Scope:** All views, states, and transitions involved in source triage and project inclusion.  
**Rule:** Every state listed here must be implemented. No states may be added without updating this document first.

---

## 1. Library Views

The source library has five filtered views. These are filter states over the same source list, not separate screens or navigation destinations.

| View Name | Filter Condition | Description |
|---|---|---|
| All Sources | No filter | Every source in the library |
| Needs Screening | No `source_inclusion` record exists | Sources imported but not yet triaged |
| Staged | `project_id IS NULL AND inclusion_status IN (candidate, included, deferred)` | Sources in the pre-project staging pool |
| Excluded | `inclusion_status = excluded` | Sources ruled out, retained with reasoning |
| In Projects | `project_id IS NOT NULL AND inclusion_status = included` | Sources committed to at least one project |

**UI rules for the library:**

- Inclusion status is displayed as a badge on each source row.
- `relevance_scope` is displayed when `inclusion_status = included`.
- `screening_depth` is displayed for all sources with an inclusion record. Sources screened at `abstract` depth carry a distinct visual indicator.
- Inclusion status is editable inline from the library view without opening the paper.
- Excluded sources are visible in the library and in the Excluded view. They are never hidden or deleted.

---

## 2. Reader States

The reader has two modes. Mode is set explicitly by the user when opening a paper. It is not inferred.

### 2.1 Full Read Mode

Default reading mode. All annotation types available. Confidence rating, spaced repetition, and writing project tagging are available. No inclusion metadata panel.

### 2.2 Triage Mode

Constrained reading mode for inclusion evaluation. Activated by the user before or after opening a paper.

**Visual requirements:**
- A persistent mode label reading "Triage Mode" is displayed in the reader header for the duration of the session.
- The label must not be dismissible.
- The inclusion metadata panel is docked and accessible without leaving the reader view.

**Inclusion metadata panel contents:**
- `inclusion_status` selector (candidate / included / excluded / deferred)
- `relevance_scope` selector (shown when status is included)
- `inclusion_reasoning` text field
- `project_role_note` text field
- `screening_depth` selector
- Save button

**Annotation behavior in triage mode:**
- All four annotation types are available.
- Every annotation created in triage mode is saved with `triage = 1`.
- No other annotation behavior changes.

---

## 3. Project Creation Flow

Project creation is initiated from the staging pool view. It has three sequential steps.

### Step 1: Source Confirmation

Displays all sources with `project_id IS NULL AND inclusion_status IN (candidate, included)`.

For each source the following are shown: title, authors, year, `inclusion_status`, `relevance_scope`, `screening_depth`, `inclusion_reasoning`.

Sources with `screening_depth = abstract` are flagged with a warning indicator. The user may proceed with them included but the warning persists.

The user can change `inclusion_status` and `relevance_scope` for any source in this step. Changes are saved to `source_inclusion` before proceeding.

At least one source with `relevance_scope = central` must be confirmed before the user can proceed to Step 2.

### Step 2: Scope Drafting

Displays a text field for the project scope statement.

Below the field, interpretation annotations captured in triage mode from all `central` sources are surfaced as reference material. These are read-only in this context. The user draws on them to write the scope statement.

The scope statement is not required to proceed but the UI prompts for it.

### Step 3: Project Seeding

Displays a summary of the project to be created: title field, source count by `relevance_scope`, scope statement preview.

On confirmation: the project record is created, all confirmed inclusion records are updated with the new `project_id`, and the user is taken to the new project view.

On cancel: no records are modified. The staging pool is unchanged.

---

## 4. A La Carte Post-Project Addition Flow

Initiated from within an existing project's source list.

The reader is opened in triage mode with additional context: the project's scope statement and the list of sources already assigned `relevance_scope = central` are displayed in a collapsible panel alongside the reader.

On session close, the user completes the inclusion metadata panel as in the standard triage flow. The `project_id` field is pre-populated with the current project's id. On save, the inclusion record is created and the source is attached to the project.

---

## 5. State Transition Map

```
[Source imported]
        |
        v
[Needs Screening]  <-- no source_inclusion record
        |
        | user opens in triage mode
        v
[candidate]
        |
        |-- user sets included + reasoning --> [included, no project_id]
        |                                              |
        |                                              | project seeding or a la carte add
        |                                              v
        |                                     [included, project_id set]
        |
        |-- user sets excluded + reasoning --> [excluded]
        |
        |-- user sets deferred             --> [deferred]
        |                                              |
        |                                              | user returns later
        |                                              v
        |                                          [candidate]
        v
[Staged pool] = filtered view of (candidate + included + deferred) where project_id IS NULL
```

---

## 6. UI Rules Summary

| Rule | Description |
|---|---|
| Triage mode indicator | Persistent, non-dismissible label in reader header |
| Inclusion panel in reader | Docked, accessible without leaving reader |
| Inline status editing | Inclusion status editable from library row without opening paper |
| Staging pool as filter | Not a separate screen. Filtered view over the library. |
| Excluded sources retained | Excluded sources visible in library and Excluded view. Never deleted. |
| Abstract screen flag | Sources with `screening_depth = abstract` carry a distinct visual indicator |
| Reasoning required | UI blocks status transition to included or excluded without reasoning text |
| Central source required | Project creation blocked until at least one central source is confirmed |
