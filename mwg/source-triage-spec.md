# source-triage-spec.md

## Engram, Source Triage and Project Inclusion Specification

**Status:** Canonical. All other triage documents derive from this one.  
**Scope:** Pre-project triage reading mode, inclusion metadata, project seeding workflow  
**Dependency:** The annotation type system (quote, paraphrase, interpretation, synthesis) must be implemented before this feature. Triage maps onto those types. It does not replace or extend them.

---

## 1. The Problem This Solves

Scholarly projects do not begin with a known source list. They begin with a candidate pool that must be evaluated before a project can be coherently scoped. Without a structured triage process two failure modes occur:

- Papers get deep-read and fully annotated before it is known whether they belong in the project, wasting annotation effort on excluded sources.
- Inclusion decisions are made informally and not recorded, making it impossible to reconstruct the reasoning later.

This spec defines a triage reading mode that is deliberately shallower than full annotation, produces structured inclusion metadata, and feeds directly into project creation. The triage read is the first pass of the full reading record, not a separate disposable process.

---

## 2. Two Modes of Inclusion

### 2.1 Pre-Project Triage, Staging Pool

Papers enter the global library and can be triaged before any project exists to receive them. The staging pool is not a separate entity. It is a filtered view over sources with `inclusion_status = candidate`. A project is created from a confirmed subset of that view once enough sources have been triaged to establish scope.

Named staging pools are not implemented in this version. Named pools are only warranted if use reveals that users need to maintain multiple independent candidate clusters simultaneously. That need is not confirmed and the additional routing, filter, and schema surface is not justified yet.

### 2.2 A La Carte Post-Project Addition

After a project exists, individual papers can be evaluated for addition against the project's established scope and argument structure. The same inclusion metadata schema applies. The difference is that `project_role_note` is now written against a known argument structure rather than a provisional one.

---

## 3. Triage Reading Mode

Triage mode is a constrained reading posture, distinct from full annotation mode. The user activates it explicitly when opening a paper. The UI signals the mode difference with a persistent visible indicator. Triage mode is not the default.

### 3.1 What Triage Mode Permits

Triage mode permits the same four annotation types as full reading, with constrained intent:

| Annotation Type | Triage Intent |
|---|---|
| Quote | Signals: this paper contains citable content worth preserving. A quote in triage is an inclusion signal. |
| Paraphrase | Signals: the core argument of this passage has been processed. A paraphrase in triage is evidence the paper's central claim is understood. |
| Interpretation | Signals: here is how this paper fits the emerging project frame. The interpretation note records the relevance reasoning explicitly. |
| Synthesis | Signals: this paper connects to another paper already in the staging pool. A synthesis note in triage is a relationship claim between candidates. |

Triage annotations carry a `triage = true` flag and are associated with the source-level inclusion record. They are not a new annotation type. When a paper is included and a full deep read follows, triage annotations become the first entries in the full reading record. They are never discarded.

### 3.2 What Triage Mode Does Not Permit

Triage mode does not prompt for confidence ratings, spaced repetition scheduling, or writing project tagging. Those belong to full reading mode and are not relevant to an inclusion decision.

### 3.3 Screening Depth

Each triage session records a `screening_depth` value on the inclusion record. This field captures how thoroughly the paper was read during triage.

| Value | Meaning |
|---|---|
| `abstract` | Only the abstract was read. No annotations captured. |
| `skim` | Introduction, headings, and conclusion reviewed. Some annotations possible. |
| `targeted` | Specific sections read in depth. Annotations captured against specific claims. |
| `full` | Full paper read in triage mode before inclusion decision. |

`screening_depth` is set by the user at the close of the triage session, not inferred automatically. It informs the project creation step: a source included on an `abstract` screen may need a deeper read before the project is final.

---

## 4. Inclusion Metadata Schema

Every paper evaluated in triage receives a source-level inclusion record. This is separate from individual annotation records. It is a structured decision document attached to the source.

### 4.1 Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `inclusion_status` | ENUM | Yes | candidate, included, excluded, deferred |
| `relevance_scope` | ENUM | On include | central, supporting, methodological, comparative, peripheral |
| `inclusion_reasoning` | TEXT | On include or exclude | Free-form note recording why the decision was made |
| `project_role_note` | TEXT | No | Anticipated role in the project argument. Provisional pre-project. |
| `screening_depth` | ENUM | On close of session | abstract, skim, targeted, full |
| `decided_at` | DATETIME | On status change | Timestamp of the inclusion or exclusion decision |

`inclusion_reasoning` must be completed before a source can move from `candidate` to `included` or `excluded`. A decision without recorded reasoning is not permitted by the UI.

### 4.2 Relevance Scope Definitions

| Value | Meaning |
|---|---|
| `central` | Foundational to the project's argument. The project cannot proceed without it. |
| `supporting` | Provides evidence or elaboration for claims anchored by central sources. |
| `methodological` | Included for its method, not its findings. |
| `comparative` | Included to establish contrast, a counterargument, or an alternative framing. |
| `peripheral` | Relevant but not load-bearing. Included for completeness or citation network reasons. |

### 4.3 Multi-Project Membership

A source may be included in more than one project with a different `relevance_scope` and `project_role_note` in each. The schema supports this via one inclusion record per source per project. A source's role in one project does not constrain its role in another.

---

## 5. Project Creation from Staging Pool

When the user initiates project creation the staging pool view surfaces all sources with `inclusion_status = candidate` or `included` and no `project_id`. The creation flow has three steps:

**Step 1, Source confirmation.** The user reviews the candidate list. `inclusion_status`, `relevance_scope`, and `screening_depth` are displayed for each source. Sources screened only at `abstract` depth are flagged. The user confirms, adjusts scopes, or excludes sources before the project is created.

**Step 2, Scope drafting.** The central sources anchor the project's scope statement. Interpretation annotations captured during triage of central sources are surfaced as drafting material for the scope statement field. The user writes or edits the scope statement before confirming.

**Step 3, Project seeding.** On confirmation the project is created with all included sources attached, relevance scopes recorded, and triage annotations carried over as the first annotations in the project. The `project_id` field is populated on all corresponding inclusion records.

---

## 6. A La Carte Post-Project Addition

When a paper is added to an existing project the triage workflow runs against the project's established scope. The UI surfaces the project's scope statement and the list of central sources already included before the triage read begins. This gives the evaluator an explicit frame of reference during the read.

The inclusion metadata fields are the same as pre-project triage. `project_role_note` is now written against a known argument structure.

---

## 7. UI Requirements

- Triage mode must be visually distinct from full reading mode. A persistent mode label is required in the reader header.
- The inclusion metadata panel must be accessible without leaving the reader view.
- Inclusion status must be editable from the source library view without opening the paper.
- The staging pool is a filtered library view, not a separate interface or navigation item.
- Excluded sources remain in the library with their exclusion reasoning visible. Exclusion is not deletion.
- Sources with `screening_depth = abstract` are visually distinguished from more thoroughly screened sources in the staging pool view.

---

## 8. Acceptance Criteria

| # | Criterion | Test Method |
|---|---|---|
| 1 | A source can exist in the library without any project association | Add source, confirm no project_id required |
| 2 | A source can be excluded without being deleted | Exclude source, confirm it remains in library with reasoning |
| 3 | A source can be included in two projects with different relevance scopes | Add source to two projects, confirm independent inclusion records |
| 4 | Triage annotations persist after project inclusion | Include source, confirm triage annotations appear in project annotation list |
| 5 | inclusion_reasoning is required before status moves to included or excluded | Attempt status change without reasoning, confirm UI blocks it |
| 6 | Project seeding populates project_id on all confirmed inclusion records | Create project from staging pool, inspect inclusion records |
| 7 | Scope statement drafting surfaces interpretation annotations from central sources | Confirm interpretation annotations appear in scope drafting step |
| 8 | Triage mode indicator is visible and persistent during triage read | Open paper in triage mode, confirm indicator present throughout |
