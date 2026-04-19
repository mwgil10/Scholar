# AGENTS.md

## Engram, Agent Task Brief: Source Triage Layer

**Applies to:** Claude Code, Codex, or any automated coding agent working on the source triage feature.  
**Authority:** This file takes precedence over general coding conventions when they conflict. Do not override these instructions based on inferences about intent or pattern-matching to similar codebases.

---

## Stack Constraints

You are working in:

- Python 3.11+
- PySide6 for all UI
- SQLite via raw `sqlite3` (no ORM, no SQLAlchemy)
- Anthropic Python SDK for AI features
- qasync for async operations (no QThread)
- python-dotenv for environment variables

Do not introduce new dependencies without flagging them explicitly in your response and waiting for confirmation. Do not use QThread. Do not use SQLAlchemy.

---

## Annotation System: Do Not Touch

The annotation type system is established and must not be modified. The four types are: `quote`, `paraphrase`, `interpretation`, `synthesis`. These are enforced at point of capture and are structural distinctions, not tags.

**Prohibited actions:**

- Do not add a fifth annotation type.
- Do not create a parallel annotation model for triage.
- Do not rename or redefine existing annotation types.
- Do not change the `position_json` schema.
- Do not alter the coordinate transform logic in the reader.

Triage annotations are existing annotation types with a `triage = 1` flag. That flag is the only addition to the annotation system. Nothing else changes.

---

## Schema Rules

- Every schema change must be implemented as a versioned migration file in `src/scholar/migrations/`.
- Migration files are named `NNN_description.sql` where NNN is a zero-padded integer one higher than the current maximum.
- Do not apply schema changes directly to the database outside the migration system.
- Do not modify existing tables except to add the `triage` column to `annotations` via migration.
- Do not add columns to `sources`, `review_projects`, or any other existing table beyond what is specified in the schema contract.
- The schema contract is in `docs/source-triage-schema.md`. It is authoritative.

---

## Source and Exclusion Rules

- A source that is excluded is not deleted. It remains in the library with its exclusion reasoning visible.
- Do not implement any deletion path for excluded sources.
- Do not hide excluded sources from the All Sources library view.

---

## Staging Pool Rule

The staging pool is a filtered view over the source library. It is not a separate table, subsystem, navigation item, or top-level UI destination. Do not create a `staging_pools` table. Do not create a named pool abstraction. The staging pool is produced by the query defined in the schema contract.

---

## Named Staging Pools: Explicitly Prohibited

Do not implement named staging pools. Do not add a `pool_id` field to `source_inclusion`. Do not create a `staging_pools` table. This feature is explicitly out of scope and the schema does not support it. If you believe named pools are necessary for a use case, flag it as a question and wait for a response. Do not implement it.

---

## Multi-Project Membership

A source may belong to multiple projects with different `relevance_scope` values in each. The schema supports this. Do not add a uniqueness constraint on `(source_id, project_id)` at the database level. Application logic enforces uniqueness for non-null `project_id` pairs. The constraint is in `db.py`, not in the migration SQL.

---

## UI Rules

- Triage mode requires a persistent, non-dismissible mode label in the reader header. Do not make it dismissible.
- The staging pool is accessed via a filter on the source library, not via a separate screen.
- Do not create new top-level navigation items for triage features.
- The inclusion metadata panel is docked in the reader during triage mode. It does not open as a dialog or modal.
- Inline status editing in the library must block transition to `included` or `excluded` without reasoning text. This enforcement is in the UI layer, not only the database layer.

---

## Implementation Order

Work through the implementation plan in sprint order. The sprint sequence is in `docs/source-triage-implementation-plan.md`. Do not begin Sprint N+1 until Sprint N passes its acceptance criteria. Do not combine sprints.

The first task is Sprint 1: schema and backend. Begin there.

---

## What to Do When Ambiguous

If a task requires a decision not covered by the spec, schema contract, UI state machine, or this brief: stop, describe the ambiguity, and ask. Do not resolve ambiguity by inventing a convention. The five documents that govern this feature are:

- `docs/source-triage-spec.md`
- `docs/source-triage-schema.md`
- `docs/source-triage-ui-states.md`
- `docs/source-triage-implementation-plan.md`
- `AGENTS.md` (this file)

If a question cannot be answered by those documents, it requires a human decision before implementation proceeds.
