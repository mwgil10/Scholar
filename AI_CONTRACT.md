# Scholar AI Contract

## Purpose

This document defines the current contract between the UI layer in `main.py`, the AI integration layer in `ai.py`, and the persistence layer that stores AI outputs.

## Current Use Case

The current AI feature is "Explain Annotation".

It is designed to:

- take a selected passage plus user interpretation
- add document and session context when available
- request a short explanation from Anthropic
- store the result in `ai_outputs`

## Current Model

Configured model in code:

- `claude-sonnet-4-6`

Reference:

- [src/scholar/ai.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\ai.py):27

## Input Contract

### Source of Inputs

`main.py` assembles context and calls:

- `explain_passage(context: dict) -> dict`

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):4311
- [src/scholar/ai.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\ai.py):5

### Required Input Fields

Required for current operation:

- `selected_text: str`
- `user_interpretation: str`

### Optional Input Fields

May be present:

- `doc_title: str`
- `reading_type: str`
- `surrounding_text: str`
- `session_intention: str`

### Input Assembly Rules

`main.py` currently assembles context as follows:

- pulls `title`, `reading_type`, and `file_path` from `documents`
- loads page text from the current/opened PDF to create `surrounding_text`
- pulls `reading_intention` from `reading_sessions` into `session_intention`

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):4341

### Recommended Stable Input Schema

```json
{
  "selected_text": "string",
  "user_interpretation": "string",
  "doc_title": "string",
  "reading_type": "string",
  "surrounding_text": "string",
  "session_intention": "string"
}
```

## Prompt Contract

### Current Prompt Structure

The current prompt is a concatenated user message with:

- document title
- reading type if present
- session intention if present
- page context if present
- selected passage
- reader interpretation if present
- instruction to respond as a thinking partner in two or three sentences

Reference:

- [src/scholar/ai.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\ai.py):12

### Current Prompt Intent

The explanation should:

- build on the user's interpretation
- remain concise
- behave more like a thinking partner than a citation engine

### Recommended Prompt Stability Rule

Any prompt revision should preserve:

- grounding in selected text
- grounding in user interpretation
- concise output length
- non-authoritative tone unless intentionally changed

## Output Contract

### Current Runtime Return Shape

`ai.py` currently returns:

```json
{
  "explanation": "string"
}
```

Reference:

- [src/scholar/ai.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\ai.py):33

### Persistence Contract

Results are stored in `ai_outputs` with:

- `document_id`
- `project_source_id`
- `annotation_id`
- `output_type = "explanation"`
- `content_json`
- `created_at`

Current `content_json` shape:

```json
{
  "explanation": "string",
  "user_interpretation": "string"
}
```

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):4319

### Recommended Stable Output Schema

For the current feature surface, this should be treated as the stable minimum:

```json
{
  "explanation": "string",
  "user_interpretation": "string"
}
```

If expanded later, add fields without removing these two keys.

## Error Contract

### Missing API Key

If `ANTHROPIC_API_KEY` is missing, `ai.py` currently returns a normal explanation payload whose value is a plain-language error string.

Current shape:

```json
{
  "explanation": "ANTHROPIC_API_KEY environment variable is not set."
}
```

Reference:

- [src/scholar/ai.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\ai.py):6

### API or Runtime Failure

If the actual AI request fails, `main.py` catches the exception and shows a blocking warning dialog.

Current behavior:

- no `ai_outputs` row is written on exception
- UI remains on the current annotation

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):4313

## UI Preconditions

Before AI explanation is run:

- the annotation must exist or be saved
- note content may be required depending on annotation type
- if no note is present, user may be prompted for interpretation

Reference:

- [src/scholar/main.py](c:\Users\mwgil\Desktop\Scholar\src\scholar\main.py):4251

## Compatibility Rules

- `main.py` must not assume additional keys from `ai.py` without updating this contract.
- `ai.py` must keep returning an object with `explanation` unless a coordinated contract migration happens.
- `ai_outputs.content_json` should remain JSON, never raw text.
- new AI output types should use a new `output_type`, not overload `"explanation"`.

## Deferred Enhancements

Potential future fields:

- `confidence`
- `follow_up_questions`
- `key_terms`
- `counterpoint`
- `source_grounding_excerpt`

These are not part of the current contract.

