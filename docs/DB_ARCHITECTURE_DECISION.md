# DB Architecture Decision

## Status

Accepted for the source triage work.

## Context

Scholar already has a working SQLite bootstrap built from `schema.sql` plus legacy
incremental repair routines in `src/scholar/db_init.py`. The source triage
specification requires new schema changes to be implemented as versioned SQL
migrations in `src/scholar/migrations/`.

## Decision

Use a hybrid database model:

- Keep `schema.sql` as the base schema for fresh installs.
- Keep existing legacy bootstrap and repair routines in `db_init.py`.
- Add a `schema_migrations` ledger table.
- Apply numbered SQL migrations from `src/scholar/migrations/` after the legacy
  bootstrap completes.
- Put all new source-triage schema changes behind migrations.
- Do not directly mutate existing tables outside migrations.

## Source Triage Schema Boundary

The current `sources` table remains the canonical source identity table. Source
triage records reference `sources.id` through the new `source_inclusion` table.

The annotation model remains unchanged except for the `annotations.triage` flag.
Triage annotations are still one of the four existing annotation types:
`quote`, `paraphrase`, `interpretation`, or `synthesis`.

## Consequences

This preserves the current app while giving new triage work an auditable schema
history. Older bootstrap routines can be simplified later, but future schema
changes should use migrations first.
