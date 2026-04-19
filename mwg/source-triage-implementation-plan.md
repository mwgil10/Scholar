# source-triage-implementation-plan.md

## Engram, Source Triage Implementation Sequence

**Status:** Active build plan.  
**Agent instruction:** Work through sprints in order. Do not begin Sprint N+1 until Sprint N passes its acceptance criteria. Do not invent scope beyond what is listed in each sprint.

---

## Prerequisites

The following must be complete before Sprint 1 begins:

- Annotation type system implemented (quote, paraphrase, interpretation, synthesis)
- `annotation_type` field present on `annotations` table
- `review_projects` table exists
- Migration system in place at `src/scholar/migrations/` with at least one prior migration file establishing the numbering convention

If any prerequisite is absent, stop and report which prerequisite is missing. Do not proceed.

---

## Sprint 1: Schema and Backend

**Goal:** Database layer fully operational. No UI changes.

**Tasks:**

1. Write migration `NNN_add_triage_flag_to_annotations.sql` per the schema contract.
2. Write migration `NNN_create_source_inclusion.sql` per the schema contract.
3. Apply both migrations. Verify with a schema inspection query.
4. In `db.py`, implement the following functions:

```
create_inclusion_record(source_id) -> id
get_inclusion_record(source_id, project_id=None) -> record or None
update_inclusion_status(record_id, status, reasoning=None, decided_at=None)
update_inclusion_scope(record_id, relevance_scope)
update_inclusion_notes(record_id, project_role_note=None, screening_depth=None)
get_staging_pool() -> list of (source + inclusion) records
get_project_inclusions(project_id) -> list of included sources for a project
seed_project_inclusions(project_id, source_ids) -> updates project_id on confirmed records
get_triage_annotations(source_id) -> list of annotations where triage=1
```

5. Add `triage=False` parameter to the existing annotation creation function. Default is False. Triage mode passes True.

**Acceptance criteria:**

- Both migrations apply cleanly to a fresh database.
- All db.py functions execute without error against test data.
- A source can be created, given an inclusion record, have its status updated to included with reasoning, and retrieved via `get_staging_pool()`.
- A source can be excluded with reasoning and retrieved separately from candidates.
- Two inclusion records for the same source with different project_ids can coexist.
- A duplicate `(source_id, project_id)` pair where project_id is non-null is rejected by application logic in `create_inclusion_record`.

---

## Sprint 2: Library Filters and Inline Status Editing

**Goal:** Staging pool and inclusion status visible and editable from the source library.

**Tasks:**

1. Add five filter tabs or filter controls to the source library view: All Sources, Needs Screening, Staged, Excluded, In Projects. These are filter states over the existing source list widget, not new screens.
2. Display `inclusion_status` badge on each source row.
3. Display `relevance_scope` on rows where `inclusion_status = included`.
4. Display `screening_depth` indicator on all rows with an inclusion record. Flag `abstract` depth distinctly.
5. Implement inline status editing from the library row: a dropdown or context menu allowing status change without opening the paper. Status change to `included` or `excluded` must require reasoning text before committing. Surface a small inline text input for reasoning when those statuses are selected.

**Acceptance criteria:**

- All five filter views return the correct source subsets.
- Excluded sources appear in the Excluded view and in All Sources. They do not appear in Staged.
- Status badge updates immediately on inline edit.
- Inline status change to `included` without reasoning text is blocked with a visible error.

---

## Sprint 3: Triage Mode in the Reader

**Goal:** User can open a paper in triage mode, capture annotations, and save inclusion metadata.

**Tasks:**

1. Add a mode toggle to the reader: Full Read and Triage. Default is Full Read.
2. In Triage mode, display a persistent non-dismissible label "Triage Mode" in the reader header.
3. Dock the inclusion metadata panel in the reader when in Triage mode. Panel contains: status selector, relevance scope selector, inclusion reasoning field, project role note field, screening depth selector, save button.
4. When the user saves the inclusion panel, call the appropriate `db.py` functions. Create a new inclusion record if none exists for this source. Update if one exists.
5. All annotations created while in Triage mode are saved with `triage = 1`. Implement this by threading the current mode through the annotation creation call path.
6. When switching from Triage to Full Read mode mid-session, prompt the user to save the inclusion record before switching. Do not switch modes silently without saving.

**Acceptance criteria:**

- Triage mode label is visible and persistent throughout a triage session.
- Annotations created in triage mode have `triage = 1` in the database.
- Annotations created in full read mode have `triage = 0`.
- Inclusion record is saved correctly on panel save.
- Mode switch without saving triggers a prompt.
- Reopening a paper with an existing inclusion record pre-populates the inclusion panel with saved values.

---

## Sprint 4: Project Creation from Staged Sources

**Goal:** User can create a project from the staging pool with source confirmation and scope drafting.

**Tasks:**

1. Add a "Create Project from Staged Sources" action to the staging pool view.
2. Implement Step 1, Source Confirmation: display all staged sources with their inclusion metadata. Allow inline scope and status adjustment. Flag abstract-screened sources. Block progression unless at least one central source is confirmed.
3. Implement Step 2, Scope Drafting: display scope statement text field. Retrieve and display interpretation annotations (triage=1, annotation_type=interpretation) from all central sources as reference material below the field.
4. Implement Step 3, Project Seeding: display summary. On confirmation, create the project record and call `seed_project_inclusions()`. On cancel, make no changes.
5. After seeding, navigate the user to the new project view.

**Acceptance criteria:**

- Project creation is blocked if no central source is confirmed.
- Interpretation annotations from central sources appear in the scope drafting step.
- On confirmation, project record is created and all confirmed inclusion records have `project_id` populated.
- On cancel, no records are modified.
- Triage annotations appear in the new project's annotation list after seeding.

---

## Sprint 5: A La Carte Post-Project Addition

**Goal:** User can add a source to an existing project through the triage workflow.

**Tasks:**

1. Add an "Add Source" action to an existing project's source list.
2. When a paper is opened for post-project triage, display the project's scope statement and central source list in a collapsible reference panel alongside the reader.
3. Pre-populate `project_id` in the inclusion metadata panel with the current project's id.
4. On save, create the inclusion record with `project_id` set. Attach the source to the project.

**Acceptance criteria:**

- Project scope statement and central sources are visible during the triage read.
- Saved inclusion record has the correct `project_id`.
- Source appears in the project's source list after save.
- A source already included in another project can be added to this one with a different `relevance_scope`.

---

## Sprint 6: Tests and Hardening

**Goal:** All acceptance criteria from Sprints 1-5 covered by tests. Edge cases handled.

**Test cases to implement:**

- Source exists in library with no inclusion record.
- Source is excluded and remains visible, not deleted.
- Source belongs to two projects with different relevance scopes.
- Triage annotations persist after project inclusion.
- `inclusion_reasoning` required before included or excluded status commits.
- Project creation blocked without a central source.
- Duplicate `(source_id, project_id)` pair rejected on non-null project_id.
- Migration applies cleanly to a fresh database.
- Migration applies cleanly on top of existing data without data loss.
