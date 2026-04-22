# Scholar Design System

## Purpose

This document defines the visual design direction for Scholar and the implementation rules that should guide UI styling in [src/scholar/main.py](src/scholar/main.py).

Scholar is a desktop research application for reading, screening, annotating, and organizing academic sources. Its interface should feel like a cognitive-science-informed learning instrument: calm, intelligent, low-noise, and trustworthy.

The highest design priority is not visual novelty or native operating-system convention. The highest priority is supporting attention, focus, comprehension, recall, and intuitive navigation during sustained academic work.

## Design Direction

### Cognitive Instrument Minimalism

Scholar should look and feel like a focused academic workbench rather than a generic desktop utility. It should be both a serious research instrument and a modern knowledge workspace, but every aesthetic decision should be subordinate to cognitive usefulness.

The target aesthetic is:

- precise
- professional
- subdued
- readable
- attention-preserving
- orientation-rich
- tactile without being glossy
- dense without feeling cluttered
- premium without feeling decorative

Visual distinctiveness should come from Scholar's purpose: learning, source vetting, focused reading, annotation, and knowledge construction. The app should not feel branded through decoration. It should feel distinct because its interface embodies its commitment to cognition.

Useful references:

- Linear for restrained density and confident control states
- Arc for quiet surfaces and low-chrome interaction
- Raycast for compact command surfaces and crisp hierarchy
- Figma desktop UI for professional panels and tools

The goal is not to copy these products. The goal is to capture their restraint, material logic, and typographic confidence while designing around the needs of academic attention.

## Product Feeling

The interface should support sustained academic attention. It should reduce extraneous cognitive load, make current state obvious, and help the user move through reading and triage workflows without losing context.

Primary feeling:

- "I can think here."

Secondary feelings:

- "The system knows what state I am in."
- "Important actions are available without shouting."
- "The document remains primary."
- "Panels help me reason, not merely store form fields."
- "I know where I am and what will happen if I click."
- "The UI gets out of the way when I am reading."

Anti-feelings:

- "This is a default Windows form."
- "Every object is yelling that it has a border."
- "The app was styled after the functionality was already done."
- "I need to decode the UI before I can read."
- "The interface is visually impressive but attention-expensive."
- "The app feels archival in a dusty or retro way."

## Visual Principles

### 0. Cognitive Usefulness Overrides Aesthetic Preference

When two visual directions are both attractive, choose the one that better supports attention, focus, comprehension, and intuitive navigation.

Design choices should be evaluated against cognitive outcomes:

- Does this reduce visual noise?
- Does this make state easier to perceive?
- Does this preserve reading flow?
- Does this help the user recover orientation after switching tasks?
- Does this make the next useful action easier to discover?
- Does this support dense information without forcing rereading or decoding?

Rules:

- Calm beats clever.
- Orientation beats novelty.
- Readability beats density.
- Stable state indicators beat hidden or moving state.
- The reading surface beats surrounding chrome.
- Interaction clarity beats native toolkit fidelity.

### 1. Reduce Stroke Dependence

Controls should not rely on permanent outlines as their primary visual separator.

Prefer:

- tonal surface changes
- spacing
- subtle elevation
- active state fill
- focus rings only when focus matters

Avoid:

- border around every button, input, card, tray, and panel
- high-contrast outlines in resting states
- nested boxes that create visual vibration

Rule:

- Resting controls may have no border or a very low-contrast border.
- Focused, selected, or active controls may use a stronger border.
- Error or blocked states may use semantic borders.

### 2. Use Radius With Intent

Rounded corners should communicate component type and scale.

Suggested radius scale:

- `radius_xs`: 4px for tiny internal affordances
- `radius_sm`: 6px for inputs and compact controls
- `radius_md`: 8px for buttons and selectors
- `radius_lg`: 10px to 12px for cards and list rows
- `radius_xl`: 14px to 16px for panels and dialogs
- `radius_pill`: full pill only for badges, status chips, and segmented controls

Avoid applying the same radius to every object.

### 3. Typography Is A Luxury Signal

Scholar should use type hierarchy to create confidence and reduce decoding effort.

Use typography to distinguish:

- section labels
- current mode
- active source
- source title
- metadata
- explanatory hints
- primary actions

Guidelines:

- Section labels should be small, uppercase or letter-spaced only when useful.
- Metadata should be legible but quiet, not tiny and grainy.
- Source titles should carry more weight than metadata.
- Empty states should use calm, centered typography with an icon only when it helps orientation.
- Typography should support fast scanning and source recognition.
- Metadata should be formatted so the eye can skip it until needed.

Avoid:

- uniformly thin labels
- dense metadata at too small a size
- over-bold button text everywhere
- using borders where typographic hierarchy would suffice

### 4. Preserve The Document As The Primary Surface

The PDF is the cognitive center of the app.

Panels and toolbars should frame the document, not compete with it.

Rules:

- The center reading canvas should stay quiet and stable.
- Toolbar controls should be compact and predictable.
- Side panels should use lower contrast than the document page.
- Annotation highlights may be visually strong only because they are anchored to reading.
- The PDF page itself should remain visually untouched by default.
- Reading-environment changes should live around the page, not on top of it, unless they are user-controlled annotation or accessibility features.
- Personalization may later allow page-adjacent preferences such as canvas tone, page shadow, margin comfort, or focus atmosphere.

### 5. Show State Calmly And Persistently

Scholar has important modes: read, triage, focus, annotation edit, project screening, and library browsing.

Mode state should be visible in a stable location, not only implied by button icons or hidden inside a panel that changes with mode.

Rules:

- The active mode should have a static status indicator.
- The button should communicate the action it will perform, not only the current state.
- Read/triage mode should be clear without relying on large text in the toolbar.
- Annotation scope should remain understandable when changing pages or documents.
- State should remain findable when panels are resized, hidden, or swapped.
- State indicators should be visually quiet enough to preserve reading calm.

### 6. Density Must Be Designed, Not Compressed

Scholar should support dense information, but density should be organized.

Prefer:

- compact rows with strong hierarchy
- selected-state contrast
- clear section breaks
- predictable truncation and ellipses
- scroll only when content truly exceeds available space

Avoid:

- cramped controls
- clipped cards when empty space exists nearby
- metadata wrapping unpredictably
- toolbars made from many adjacent boxed buttons

### 7. Custom UI Is Allowed When It Improves Cognition

Scholar does not need to preserve default Windows control expectations when a custom control improves clarity, focus, or visual quality.

Rules:

- Use platform conventions where they reduce confusion.
- Depart from platform conventions when default controls add visual noise or weaken hierarchy.
- Custom controls must still communicate affordance clearly.
- Premium should mean calmer, clearer, and more intentional, not merely more stylized.

## Semantic Tokens

The current QSS uses many one-off palette keys. Future styling should move toward semantic tokens.

### Surface Tokens

- `surface_app`: root app background
- `surface_canvas`: reading canvas around PDF pages
- `surface_paper`: warm, clean paper-adjacent surface for light mode
- `surface_library`: warm library/workbench panel tone without retro yellowing
- `surface_panel`: left and right panel background
- `surface_panel_alt`: nested panel or workspace background
- `surface_raised`: card/list row resting surface
- `surface_sunken`: input resting surface
- `surface_control`: button/select resting surface
- `surface_control_hover`: hover surface
- `surface_control_pressed`: pressed surface
- `surface_selected`: selected row/card surface
- `surface_accent_soft`: subtle accent action surface

### Border Tokens

- `border_none`: no visible border
- `border_subtle`: low-contrast structural edge
- `border_control`: resting control edge, used sparingly
- `border_hover`: hover edge
- `border_focus`: keyboard/input focus ring
- `border_selected`: selected item edge
- `border_accent`: primary or mode-specific edge

### Text Tokens

- `text_primary`: source titles and high-value labels
- `text_secondary`: metadata and supporting labels
- `text_tertiary`: hints, disabled-adjacent notes
- `text_inverse`: text on strong filled surfaces
- `text_accent`: active mode, primary action, link-like affordance
- `text_warning`: blocked or caution state

### State Tokens

- `state_idle`
- `state_active`
- `state_dirty`
- `state_saved`
- `state_blocked`
- `state_read`
- `state_triage`
- `state_focus`

These should map to fill, text, and border choices rather than becoming hard-coded colors in each selector.

## Component Rules

### Toolbar

The toolbar should feel like an instrument strip, not a row of legacy utility buttons.

Rules:

- Group controls through spacing and quiet trays, not heavy outlines.
- Icon buttons need breathing room.
- Adjacent controls should avoid double borders.
- Active mode buttons should use a filled or tonal selected state.
- Utility buttons should be quieter than workflow buttons.
- Search should read as a field embedded into the toolbar, not a bordered rectangle floating beside others.

Avoid:

- many small outlined capsules in a row
- strong borders on every icon button
- large mode text inside cramped controls

### Buttons

Resting buttons should feel tactile through surface tone, not hard outlines.

Button hierarchy:

- Primary: filled accent-soft surface, stronger text, subtle border only if needed
- Secondary: neutral raised surface, quiet text
- Utility icon: transparent or very quiet surface, hover reveals affordance
- Destructive: reserved for future deletion flows, never implied by generic accent

Rules:

- Hover should lighten or lift the surface.
- Pressed should deepen the surface.
- Focus should use a clear focus ring.
- Disabled should reduce text contrast and surface contrast.

### Inputs

Inputs should be calm at rest and clear on focus.

Rules:

- Resting inputs use `surface_sunken` and a subtle or invisible border.
- Focus state gets the strongest input border.
- Placeholder text uses `text_tertiary`.
- Text fields in annotation workspace may use a slightly different surface to distinguish editable thought space.

Avoid:

- bright permanent borders
- identical styling for active inputs and passive status pills

### Selects And Filters

Dropdowns should communicate that they are selectable without looking like default toolkit boxes.

Rules:

- Use a quiet filled surface.
- Align text and dropdown affordance cleanly.
- Use selected-state tone for active filters.
- Filter controls should feel related as a group.

### Panels

Panels should frame workflows without boxing every child.

Rules:

- Main side panels use `surface_panel`.
- Nested workspaces use `surface_panel_alt`.
- Cards inside panels use `surface_raised`.
- Structural borders should mostly be reserved for panel edges and splitters.
- Use internal spacing and section headers instead of nested outlines.

### List Rows And Cards

Document rows and annotation rows are not generic list cells. They are cognitive objects.

Rules:

- Title gets the strongest hierarchy.
- Metadata is secondary but readable.
- Active row uses selected fill and maybe a left accent or subtle edge.
- Rows should not clip text when available space exists.
- Truncation should be deliberate and consistent.
- Hover should be subtle.

Document rows:

- Prioritize source title.
- Show project/triage state as structured metadata.
- Avoid grainy tiny metadata.

Annotation rows:

- Prioritize type, page, confidence, and note/selection preview.
- Multi-part selections should remain visible in metadata.
- The selected annotation should be easy to relocate.

### Status Indicators

Status should be quiet, stable, and useful.

Rules:

- Mode status belongs in a consistent top location.
- Workspace status can exist locally, but it must not be the only mode signal.
- State labels should use tonal chips rather than bordered boxes.

Examples:

- `Mode: Read`
- `Mode: Triage`
- `Editing annotation`
- `Unsaved source details`
- `Saved`

### Dialogs

Dialogs should feel like focused task surfaces.

Rules:

- Use stronger heading hierarchy.
- Use tables only when tabular comparison is the core task.
- Avoid default grid harshness when reviewing imports.
- Primary action should be obvious but restrained.
- Dialog width should match task complexity.

Key dialogs:

- PDF import review
- Add existing screened source
- Create project from staged sources
- Metadata cleanup

## Light And Dark Mode

Scholar should support both modes, but neither should feel like a theme swap pasted onto default widgets.

Light mode is the default identity. Dark mode should be an equal alternative, not a secondary afterthought.

Light mode:

- warm-neutral app background
- paper and library tones that feel clean, current, and attentive
- soft panel surfaces
- low-contrast borders
- strong dark text
- blue accent used sparingly
- avoid dirty beige, sepia nostalgia, or retro archive coding

Dark mode:

- dark blue-gray base
- raised surfaces through tone, not glowing borders
- text contrast high enough for long reading
- accent states clear but not neon
- equal care and completeness with light mode

Shared rule:

- Do not make every border more visible in dark mode. Dark mode often needs fewer visible strokes, not more.
- Keep interaction hierarchy consistent across modes even when colors differ.

## Brand Distinctiveness

Scholar should be subtly distinct.

The distinction should come from:

- cognitive-science-informed workflows
- calm learning-oriented language
- stable orientation cues
- warm but clean research surfaces
- thoughtful annotation and triage states
- restrained typography and iconography

The distinction should not come from:

- decorative motifs
- loud color branding
- playful gloss
- OS-default nostalgia
- excessive custom chrome

## Implementation Strategy

### Current Styling Location

Most styling currently lives in `PDFViewer.apply_theme()` in [src/scholar/main.py](src/scholar/main.py).

The app already uses object names and properties extensively:

- `#Ribbon`
- `#RibbonShell`
- `#RibbonTray`
- `#RibbonButton`
- `#LibraryPanel`
- `#InspectorPanel`
- `#ScopeSelector`
- `#ActiveRecordCard`
- `#InfoList`
- `#SavedAnnotationsPanel`
- `#AnnotationWorkspacePanel`
- `#WorkspaceStatusLabel`
- `#AccentButton`

This makes a staged design-system refactor feasible.

### Refactor Order

1. Add semantic palette aliases while preserving existing keys.
2. Introduce radius and spacing variables in `apply_theme()`.
3. Restyle common controls: buttons, inputs, selects, lists, status labels.
4. Restyle toolbar groups.
5. Restyle left project panel.
6. Restyle right inspector and annotation workspace.
7. Restyle dialogs.
8. Remove obsolete one-off palette keys only after the UI is stable.

### Safety Rules

- Do not change workflow behavior during visual refactors unless explicitly intended.
- Keep light and dark mode changes paired.
- Avoid broad QSS selectors when an object-name selector is safer.
- Commit visual milestones separately.
- After every visual pass, run the test suite and compile check.
- If a visual change makes the app prettier but harder to scan, revert or revise it.
- Preserve PDF content by default; personalization should be opt-in.

## QA Checklist

Use this checklist after each major visual pass.

- App launches in light mode.
- App launches in dark mode.
- No document loaded state looks intentional.
- PDF reading state preserves document primacy.
- Left panel document list is readable at narrow and normal widths.
- Current source card does not clip awkwardly.
- Source organizer save button reads as clickable.
- Read mode and triage mode are clearly distinguishable.
- Annotation workspace edit mode remains usable.
- Saved annotation list uses available vertical space before scrolling.
- Multi-part annotation metadata remains visible.
- Import review dialog is readable.
- Create project from staged sources dialog is readable.
- Focus/read mode keeps attention on the document.
- Toolbar controls do not overflow when the window is maximized or narrowed.

## Near-Term Implementation Milestones

### Milestone 1: Token Foundation

Add semantic token aliases and radius/spacing variables. No major visual change yet.

### Milestone 2: Core Controls

Restyle buttons, inputs, selects, list rows, and status labels.

### Milestone 3: Toolbar Modernization

Reduce boxed-control clutter and make mode/action buttons clearer.

### Milestone 4: Panel Modernization

Apply the new material logic to the left project panel and right inspector.

### Milestone 5: Dialog Modernization

Bring import and project-creation dialogs into the same visual language.

## Decision Log

- The chosen direction is `Cognitive Instrument Minimalism`.
- The design should optimize cognitive support over visual flourish.
- Attention, focus, comprehension, recall, and intuitive navigation are the highest design priorities.
- Scholar should be both a serious research instrument and a modern knowledge workspace.
- Light mode is the default identity; dark mode is an equal alternative.
- Brand distinctiveness should be subtle and rooted in Scholar's commitment to learning and cognitive science.
- Reading calm is more important than constant command visibility.
- Warm paper/library tones are preferred, but they should feel clean and current rather than dirty, old, or retro.
- The PDF reading surface remains visually primary.
- The PDF page itself should remain untouched by default, with personalization handled as opt-in.
- Borders are no longer the default mechanism for affordance.
- Mode state should be visible in a stable location.
- Native Windows expectations may be overridden when custom UI improves visual quality, intuition, or cognitive support.
- Visual refactors should proceed in separate commits from workflow changes.
