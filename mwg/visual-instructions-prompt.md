# Prompt: Scholar App — Visual Instruction Set

Paste this entire prompt into ChatGPT (GPT-4o with DALL-E) or Claude (with artifact/image generation). Ask for one image at a time and confirm each before moving to the next.

---

## Meta-instruction (give this first)

> I'm building a visual onboarding guide for a desktop academic reading app called **Scholar**. I need a set of **7 flat-design instructional illustrations** — clean, minimal, with visible UI elements, annotation callouts, and color-coded flows. Style: like a Notion or Linear product explainer — neutral background (#F5F4F0), crisp sans-serif labels, muted accent palette (slate blue for UI chrome, amber for highlights, sage green for actions, coral for warnings). Each image should be **1200×800px, landscape**.
>
> The images should function as a visual manual — someone who has never opened the app should understand the app's purpose, layout, core workflows, and conceptual model from these images alone. Text labels in the images are encouraged. Diagrams can be schematic (not photorealistic).

---

## Image 1 — "What Scholar Is For" (Conceptual Purpose)

> **Image 1 of 7: The Research Pipeline**
>
> Create a horizontal pipeline diagram showing how academic research actually works — and where Scholar fits. Three stages, each as a labeled card:
>
> **Stage 1: Discovery**
> - Label: "Collect sources"
> - Visual: stack of PDFs, a browser tab, a folder
> - Note: "10s of papers you might use"
>
> **Stage 2: Screening (Scholar's first job)**
> - Label: "Triage & screen"
> - Visual: a funnel icon with sources going in, fewer coming out
> - Callout: "Read each source lightly. Decide: In, Out, or Later."
> - Highlight this stage with a subtle amber glow border
>
> **Stage 3: Deep Reading (Scholar's second job)**
> - Label: "Annotate & synthesize"
> - Visual: open document with highlights and margin notes
> - Callout: "Build a project from screened sources. Annotate deeply."
>
> **Stage 4: Output**
> - Label: "Write & export"
> - Visual: document with footnotes, bibliography list
> - Note: "Annotated bibliography, reading summary, writing project"
>
> Beneath the pipeline: a label — *"Scholar handles Stages 2 and 3. Your sources stay in one place across both."*

---

## Image 2 — "How Scholar Organizes Your Work" (Data Hierarchy)

> **Image 2 of 7: The Data Model**
>
> Create a clean hierarchy tree diagram showing the nesting of concepts. Use indentation + connecting lines + icon badges per level.
>
> **Level 1 — Library** (icon: bookshelf)
> - "Every PDF you've ever imported. Global. Permanent."
> - Note: "Sources live here independently of projects"
>
> **Level 2 — Source** (icon: single document)
> - "One paper. Has metadata (title, author, year, DOI)."
> - Two sub-branches from each source:
>
>   **Branch A — Inclusion Record** (icon: clipboard with checkmark)
>   - "Pre-project screening: Is this in or out?"
>   - Sub-item: "Inclusion status: Candidate → Included / Excluded / Deferred"
>   - Sub-item: "Relevance scope: Central / Supporting / Methodological / Comparative / Peripheral"
>   - Sub-item: "Screening depth: Abstract / Skim / Targeted / Full"
>   - Sub-item: "Reasoning (required to commit)"
>
>   **Branch B — Project Source** (icon: folder with label)
>   - "Once included in a project, source joins here"
>   - Sub-items: Annotations, Reading Sessions, AI Outputs
>
> **Level 3 — Project** (icon: folder, shown as sibling to Library)
> - "A named review effort. Contains only screened, included sources."
> - Sub-item: "Annotations scoped to this project"
>
> **Level 4 — Annotation** (icon: highlight marker)
> - "Quote / Paraphrase / Interpretation / Synthesis"
> - Sub-items: Tags, Confidence, Writing Project link, AI Explanation
>
> At bottom: a side note box — *"Writing Projects cut across everything: an annotation from any source can be linked to a writing project."*

---

## Image 3 — "The App Layout" (UI Map)

> **Image 3 of 7: The Interface**
>
> Draw a schematic of the three-panel desktop layout. Use rectangles with internal labels and callout arrows.
>
> **Top ribbon (full width, thin bar):**
> - Left cluster: [≡ Library toggle] [+ Open PDF ▾]
> - Center cluster: [◀ Prev] [Page 3 / 47] [▶ Next] [─────slider─────] [🔍 Search…]
> - Right cluster: [? Explain] [● Session] [⋯ More] | [📖 Mode] [👁 Focus] [☀ Theme] [◧ Inspector]
> - Label each cluster: "Library controls" / "Navigation" / "Tools & Display"
>
> **Left panel (Library, 280px wide):**
> - Section header: "Project Space"
> - Dropdown: "[ My Lit Review ▾ ] [New ▾]"
> - Section header: "Documents"
> - Filter bar: "[ All Sources ▾ ]"
> - List of document rows (show 3 rows with title/author/year)
> - Callout arrow: "Filter by screening status"
> - Callout arrow: "Click to open a source"
> - At the bottom edge: tiny resize grip "⠿"
>
> **Center panel (PDF reader, dominant):**
> - Rendered page (gray rectangle)
> - Yellow highlight band across a line of text
> - Small selection rectangle (dashed border) over a passage
> - Callout: "Drag to select text → creates annotation draft"
>
> **Right panel (Inspector, 300px wide):**
> - Section: "Saved annotations" with scope selector "[ This document ▾ ]"
> - 2-3 annotation rows (type badge + snippet)
> - Divider
> - Section: "Annotation workspace"
> - Fields: Type dropdown, Tags, Note field, Save button
> - Callout arrow: "Workspace is where you draft; list above is what you've saved"
>
> Add a label in the margin: *"All three panels are collapsible. Focus Mode hides everything except the page."*

---

## Image 4 — "Triage Mode vs. Full Mode" (Reader Mode States)

> **Image 4 of 7: The Two Reading Modes**
>
> Split the image in half vertically. Left half = Triage Mode. Right half = Full Reading Mode. Label each half with a large header. A small toggle icon in the center indicates you switch between them with one button.
>
> **Left half — Triage Mode** (amber accent)
> - Header: "📋 Triage Mode — Screening"
> - Subtitle: "Use when you don't yet know if a source belongs in your project"
> - Right inspector shows the **Inclusion Metadata panel**:
>   - "Inclusion status: [ Candidate ▾ ]"
>   - "Screening depth: [ Skim ▾ ]"
>   - "Relevance scope: [ Supporting ▾ ]"
>   - "Reasoning: [_______________]"
>   - "[Save Inclusion Metadata]"
> - Annotation types available: Quote, Paraphrase, Interpretation, Synthesis (labeled "lightweight")
> - Callout: "Annotations marked as triage — they travel with the source, not locked to a project yet"
>
> **Right half — Full Reading Mode** (slate blue accent)
> - Header: "📖 Full Mode — Deep Reading"
> - Subtitle: "Use when source is in a project and you're reading carefully"
> - Right inspector shows **Annotation Workspace**:
>   - Type selector, Tags, Confidence selector, Writing Project link
>   - "[Save Annotation]"
> - Callout: "All annotation types fully available with confidence, writing project tagging, AI explanation"
>
> At the bottom center: a note — *"You can switch modes at any time. Triage annotations are preserved when you switch to Full mode."*

---

## Image 5 — "The Triage Workflow" (Screening Flow)

> **Image 5 of 7: Screening Sources Before Building a Project**
>
> Create a numbered step-by-step flow diagram. Horizontal steps connected by arrows. Use small UI sketch thumbnails inside each step box.
>
> **Step 1: Import sources**
> - Action: Click [+ Open PDF ▾] → "Add PDFs to Library…" or "Add Folder to Library…"
> - Visual: folder → library list
> - Note: "Sources enter as 'Needs Screening'"
>
> **Step 2: Open source in Triage Mode**
> - Action: Click source in library → click [📋 mode button]
> - Visual: document opens, right panel shows Inclusion Metadata panel
> - Library filter shows: "[ Needs Screening ▾ ]"
>
> **Step 3: Read and take lightweight notes**
> - Action: Select text → annotation type → save
> - Visual: highlighted text, annotation workspace with "triage" label
> - Note: "Focus: abstract, intro, conclusion. Don't go deep yet."
>
> **Step 4: Set screening metadata**
> - Action: Fill in Inclusion Metadata panel
> - Visual: panel with status = "Included", depth = "Skim", reasoning filled in
> - Callout: "Reasoning is required before setting Included or Excluded"
>
> **Step 5: Repeat for all sources**
> - Visual: library filter = "Staged" showing candidate/included/deferred sources as a list
> - Note: "Use 'Staged' filter to see your screening queue"
>
> **Step 6: Create project from staged sources**
> - Action: Click [New ▾] → "From Staged Sources…"
> - Visual: dialog with 3 steps — (1) Confirm sources, (2) Draft scope statement, (3) Create project
> - Note: "Scope statement is seeded from your Interpretation annotations on central sources"
>
> **Step 7: Project created**
> - Visual: project combo shows new project name; library shows "In Projects" filter active
> - Arrow looping back to a "Full Mode" reading icon

---

## Image 6 — "The Annotation Workflow" (Deep Reading Flow)

> **Image 6 of 7: Creating and Using Annotations**
>
> A two-part diagram. Top part: how to CREATE an annotation (linear steps). Bottom part: the four annotation types as a 2×2 grid.
>
> **Top — Creating an annotation (7 micro-steps in a row):**
>
> Step 1: Select text by dragging on page → dashed selection rectangle appears
> Step 2: Selected text auto-fills "Selected text" field in workspace
> Step 3: Choose annotation type from dropdown (Paraphrase / Interpretation / Quote / Synthesis)
> Step 4: Write a note in "Note" field (optional but encouraged)
> Step 5: Add tags (system tags shown as chips: theory, method, finding, limitation, contradiction, definition, evidence)
> Step 6: Set confidence (low / medium / high) and optionally link to Writing Project
> Step 7: Click [Save Annotation] → highlight appears on page, row appears in saved list
>
> Add a small branch from Step 7: "Click an existing annotation in the list → workspace populates → edit → save again (updates in place)"
>
> **Bottom — The four annotation types (2×2 grid):**
>
> | **Quote** (amber) | **Paraphrase** (sage) |
> |---|---|
> | Verbatim passage preserved | Author's idea in your words |
> | *Use for: citable evidence, key definitions* | *Use for: comprehension, restating arguments* |
>
> | **Interpretation** (blue) | **Synthesis** (coral) |
> |---|---|
> | Your assessment of what it means | Connection between this source and others |
> | *Use for: relevance judgments, scope fit* | *Use for: cross-source relationships, contrasts* |
>
> Note below grid: *"Interpretation annotations from 'Central' sources are used to seed your project scope statement during project creation."*

---

## Image 7 — "Modes, States, and Quick Reference" (Summary Cheat Sheet)

> **Image 7 of 7: State Map + Quick Reference**
>
> A compact reference card layout. Three sections:
>
> **Section A — Mode/State Map (left third, flowchart style):**
>
> Show these states as labeled nodes with transition arrows:
>
> - [Library View] →(click source)→ [Document Open]
> - [Document Open] →(click 📋)→ [Triage Mode]
> - [Document Open] →(already in project)→ [Full Mode]
> - [Triage Mode] →(click 📋 again)→ [Full Mode]
> - [Full Mode] →(F11)→ [Focus Mode — panels hidden]
> - [Focus Mode] →(Esc or F11)→ [Full Mode]
> - [Full Mode] →(click annotation in list)→ [Editing Existing]
> - [Editing Existing] →(save)→ [Full Mode]
>
> **Section B — Annotation Scope Selector (center third):**
>
> Show the "Saved annotations" scope dropdown with three options:
> - "Page 3" — only annotations on current page
> - "This document" — all annotations in this source
> - "Project" — all annotations across all sources in the current project
>
> Below: "Scope only affects what you *see* in the list — it doesn't change where annotations are saved."
>
> **Section C — Keyboard Shortcuts & Toolbar Quick Reference (right third):**
>
> Two-column table:
>
> | Key | Action |
> |---|---|
> | ← / → | Previous / Next page |
> | Home / End | First / Last page |
> | Ctrl+L | Toggle library panel |
> | Ctrl+F | Focus search box |
> | F3 / Shift+F3 | Next / Prev search result |
> | F11 | Toggle focus mode |
> | Esc | Clear search / exit focus |
>
> Below: Toolbar icon legend (small icon + label pairs):
> - [≡] Library toggle
> - [+▾] Open/import PDFs
> - [?] AI Explain
> - [📖/📋] Full / Triage mode toggle
> - [👁] Focus mode
> - [☀/🌙] Theme toggle
> - [◧] Inspector toggle
