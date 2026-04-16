# Scholar Export Specification

## Purpose

This document defines the current structure of Scholar's markdown export outputs.

It exists so exports can be treated as stable user-facing artifacts rather than incidental strings assembled in code.

## Current Export Types

Scholar currently supports three export types:

1. Reading Summary
2. Annotated Bibliography
3. Writing Project Export

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):3785

## Common Export Rules

### Output Format

- plain markdown
- UTF-8 text file
- trailing newline included

### File Save Behavior

- user chooses output path through a save dialog
- output file is written by `write_export_file`

Reference:

- [src/scholar/export.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\export.py):502

### Annotation Type Labels

Current annotation labels:

- `quote` -> `Direct Quote`
- `paraphrase` -> `Paraphrase`
- `interpretation` -> `Interpretation`
- `synthesis` -> `Synthesis`

Reference:

- [src/scholar/export.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\export.py):8

## Citation Formatting Contract

### Current Status

Scholar currently generates a pragmatic citation line from available metadata.

It is not yet a formally validated APA engine.

### Current Citation Inputs

Possible metadata fields:

- authors / author
- year
- journal / source / publisher
- volume
- issue
- pages
- doi
- url

Reference:

- [src/scholar/export.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\export.py):56

### Current Rule

Citation lines are "best-effort academic style," not guaranteed APA-compliant output.

If strict APA is required later, that should be a separate export enhancement.

## Export Type 1: Reading Summary

### Function

- `render_reading_summary(db_path, document_id, project_source_id)`

Reference:

- [src/scholar/export.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\export.py):365

### File Naming

Pattern:

- `reading-summary-<slug>.md`

### Structural Template

```md
# Reading Summary: <title>

Citation: <citation line>
Status: <status>
Priority: <priority>
Reading type: <reading type>
Project space: <project title>        # optional
Source file: <file path>              # optional

Total annotations: <count>

### <Annotation Type> | Page <n> | Confidence: <level>
Writing project: <title>              # optional
Selected text:
> <selected text>                     # optional
Paraphrase:                           # type-specific label
<note content>                        # optional
AI explanation:
<text>                                # optional
```

### Required Top-Level Fields

- title
- citation line or fallback title
- status
- priority
- reading type
- total annotations

### Annotation Block Rules

- each annotation begins with `###`
- page number is 1-based for display
- quote text is rendered as markdown blockquote
- note label changes by annotation type
- AI explanation is appended only if available

## Export Type 2: Annotated Bibliography

### Function

- `render_annotated_bibliography(db_path, review_project_id)`

Reference:

- [src/scholar/export.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\export.py):283

### File Naming

Pattern:

- `annotated-bibliography-<slug>.md`

### Structural Template

```md
# Annotated Bibliography: <project title>

Project space: <project title>
Research question: <question>         # optional

Total sources: <count>

## <source title>

<citation line>

<summary paragraph>

<evaluation paragraph>

Status: <status> | Priority: <priority> | Reading type: <type> | Annotations: <count>
```

### Entry Rules

- one `##` section per source
- source order is alphabetical by display/canonical title
- summary paragraph comes from progressive summary if present, otherwise fallback synthesis logic
- evaluation paragraph is built from interpretation/synthesis notes first

### Current Summary Contract

The export currently synthesizes summary/evaluation text from:

- latest `progressive_summaries.rolling_summary` when available
- otherwise selected annotation notes or selected text

This is a generated summary artifact, not a verbatim notes dump.

## Export Type 3: Writing Project Export

### Function

- `render_writing_project_export(db_path, writing_project_id)`

Reference:

- [src/scholar/export.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\export.py):396

### File Naming

Pattern:

- `writing-project-export-<slug>.md`

### Structural Template

```md
# Writing Project Export: <project title>

Type: <type>
Status: <status>
Linked annotations: <count>

## Paraphrases

### <source title> | Page <n> | Confidence: <level>
Project space: <project title>        # optional
Citation: <citation line>             # optional
Selected text:
> <selected text>                     # optional
Your note:
<note content>                        # optional
```

### Grouping Rules

Annotations are grouped into these sections in this order:

1. Paraphrases
2. Interpretations
3. Synthesises / Synthesis notes
4. Direct Quotes

Current implementation uses:

- `paraphrase`
- `interpretation`
- `synthesis`
- `quote`

in that order.

### Ordering Rules Within a Section

Current sort order:

1. annotation type group
2. source title
3. page number
4. created_at

## Current Stability Level

### Stable Enough to Rely On

- export type names
- file naming patterns
- heading hierarchy
- inclusion of annotation type / page / confidence in annotation-level sections

### Not Yet Formally Stable

- strict citation style compliance
- exact prose-generation behavior for summary/evaluation text
- wording of empty states

## Empty State Rules

### Reading Summary

- if no annotations, include `No annotations yet.`

### Annotated Bibliography

- if no sources, include `No sources are attached to this project yet.`

### Writing Project Export

- if a section has no annotations, include `None yet.`

## Quality Guardrails

- Do not change heading levels casually.
- Do not remove citation lines without replacing the citation contract.
- Do not collapse annotation types into a single undifferentiated list.
- Do not switch page numbering to zero-based display.
- If strict APA output is introduced, do it as an explicit formatting upgrade, not a silent behavioral drift.

