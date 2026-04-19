# source-triage-schema.md

## Engram, Source Triage Data Contract

**Status:** Normative. This file is the authoritative schema definition for the triage layer.  
**Dependency:** Existing `sources` and `annotations` tables. Existing `review_projects` table. Do not alter those tables.  
**Migration rule:** Every schema change in this document must be implemented as a versioned migration script in `src/scholar/migrations/`. Migration files are named `NNN_description.sql` where NNN is a zero-padded integer incrementing from the current highest migration number. Do not apply schema changes directly to the database outside the migration system.

---

## 1. Existing Tables Referenced (Do Not Modify)

```sql
-- Referenced but not modified by this feature
sources (id, title, authors, year, doi, pdf_path, library_status, created_at, updated_at)
annotations (id, source_id, annotation_type, note_content, position_json, triage, created_at, updated_at)
review_projects (id, title, scope_statement, status, created_at, updated_at)
```

The `triage` boolean column on `annotations` is the only addition to an existing table. It is added via migration.

---

## 2. Migration: Add Triage Flag to Annotations

**File:** `src/scholar/migrations/NNN_add_triage_flag_to_annotations.sql`

```sql
ALTER TABLE annotations ADD COLUMN triage INTEGER NOT NULL DEFAULT 0;
```

`triage = 1` means the annotation was captured during a triage read session. `triage = 0` is the default for all existing and future full-read annotations. This is the only change to the annotations table.

---

## 3. New Table: source_inclusion

**File:** `src/scholar/migrations/NNN_create_source_inclusion.sql`

```sql
CREATE TABLE IF NOT EXISTS source_inclusion (
    id                  TEXT PRIMARY KEY,
    source_id           TEXT NOT NULL,
    project_id          TEXT,
    inclusion_status    TEXT NOT NULL DEFAULT 'candidate',
    relevance_scope     TEXT,
    inclusion_reasoning TEXT,
    project_role_note   TEXT,
    screening_depth     TEXT,
    decided_at          DATETIME,
    created_at          DATETIME NOT NULL,
    updated_at          DATETIME NOT NULL,

    FOREIGN KEY (source_id) REFERENCES sources(id),
    FOREIGN KEY (project_id) REFERENCES review_projects(id),

    CHECK (inclusion_status IN ('candidate', 'included', 'excluded', 'deferred')),
    CHECK (relevance_scope IN ('central', 'supporting', 'methodological', 'comparative', 'peripheral') OR relevance_scope IS NULL),
    CHECK (screening_depth IN ('abstract', 'skim', 'targeted', 'full') OR screening_depth IS NULL)
);

CREATE INDEX idx_source_inclusion_source_id ON source_inclusion(source_id);
CREATE INDEX idx_source_inclusion_project_id ON source_inclusion(project_id);
CREATE INDEX idx_source_inclusion_status ON source_inclusion(inclusion_status);
```

---

## 4. Field Contracts

### source_inclusion.id
UUID, generated at record creation. TEXT type per existing Engram schema convention.

### source_inclusion.source_id
Foreign key to `sources.id`. Not null. A source must exist before it can have an inclusion record.

### source_inclusion.project_id
Nullable. NULL means the record is a pre-project staging pool entry. Non-null means the source has been committed to a specific project. Populated during project seeding or a la carte addition.

### source_inclusion.inclusion_status

| Value | Meaning |
|---|---|
| `candidate` | Evaluated but not yet committed |
| `included` | Confirmed for the project or staging pool |
| `excluded` | Ruled out, with recorded reasoning |
| `deferred` | Return to this source later |

Application logic must enforce: `inclusion_reasoning` must be non-null and non-empty before status transitions to `included` or `excluded`. The database CHECK constraint does not enforce this. The application layer does.

### source_inclusion.relevance_scope

| Value | Meaning |
|---|---|
| `central` | Foundational. Project cannot proceed without it. |
| `supporting` | Evidence or elaboration for central source claims. |
| `methodological` | Included for method, not findings. |
| `comparative` | Contrast, counterargument, or alternative framing. |
| `peripheral` | Relevant but not load-bearing. |

Required when `inclusion_status = included`. Nullable otherwise.

### source_inclusion.screening_depth

| Value | Meaning |
|---|---|
| `abstract` | Abstract only. No annotations required. |
| `skim` | Introduction, headings, conclusion. Some annotations possible. |
| `targeted` | Specific sections read in depth. |
| `full` | Full paper read in triage mode before decision. |

Set by the user at the close of the triage session. Not inferred automatically.

### source_inclusion.inclusion_reasoning
Free-form text. Required before `included` or `excluded` status is committed. No minimum length enforced by the database. Application layer enforces non-empty.

### source_inclusion.project_role_note
Free-form text. Nullable. Describes the anticipated role in the project's argument structure. Provisional pre-project. Written against established scope in post-project addition.

### source_inclusion.decided_at
Set when `inclusion_status` transitions to `included` or `excluded`. Nullable until that transition occurs.

---

## 5. Multi-Project Membership

One source may have multiple `source_inclusion` records, one per project. The combination of `(source_id, project_id)` is not enforced as unique by the database to allow pre-project records (where `project_id` is NULL and multiple NULL values are permitted by SQLite). Application logic must prevent duplicate `(source_id, project_id)` pairs where `project_id` is non-null.

```sql
-- Application-level check before insert (not a DB constraint due to nullable project_id)
SELECT id FROM source_inclusion
WHERE source_id = ? AND project_id = ?;
-- If result exists, update rather than insert.
```

---

## 6. Staging Pool Query

The staging pool view is produced by this query. It returns all sources that have been triaged but not yet assigned to a project.

```sql
SELECT
    s.id,
    s.title,
    s.authors,
    s.year,
    si.inclusion_status,
    si.relevance_scope,
    si.screening_depth,
    si.inclusion_reasoning,
    si.updated_at
FROM sources s
JOIN source_inclusion si ON s.id = si.source_id
WHERE si.project_id IS NULL
AND si.inclusion_status IN ('candidate', 'included', 'deferred')
ORDER BY si.updated_at DESC;
```

---

## 7. Project Seeding Query

When a project is created from staged sources, this update commits the inclusion records to the project.

```sql
UPDATE source_inclusion
SET project_id = ?,
    updated_at = ?
WHERE source_id IN (/* confirmed source ids */)
AND project_id IS NULL
AND inclusion_status = 'included';
```

---

## 8. Triage Annotations Query

Retrieves all annotations produced during triage for a given source.

```sql
SELECT *
FROM annotations
WHERE source_id = ?
AND triage = 1
ORDER BY created_at ASC;
```
