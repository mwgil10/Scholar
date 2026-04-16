-- Schema extracted from SCHOLAR_BOOTSTRAP.md (core tables)

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT,
    file_path TEXT,
    source_url TEXT,
    reading_type TEXT,
    status TEXT,
    priority INTEGER,
    total_pages INTEGER,
    last_page_read INTEGER,
    progress_pct REAL,
    citation_metadata TEXT,
    created_at DATETIME,
    updated_at DATETIME
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    file_path TEXT,
    canonical_title TEXT,
    source_url TEXT,
    citation_metadata TEXT,
    doc_fingerprint TEXT,
    created_at DATETIME,
    updated_at DATETIME
);

CREATE TABLE IF NOT EXISTS project_sources (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES review_projects(id),
    source_id TEXT NOT NULL REFERENCES sources(id),
    legacy_document_id TEXT REFERENCES documents(id),
    display_title TEXT,
    status TEXT,
    priority INTEGER,
    reading_type TEXT,
    local_notes TEXT,
    created_at DATETIME,
    updated_at DATETIME
);

CREATE TABLE IF NOT EXISTS reading_sessions (
    id TEXT PRIMARY KEY,
    document_id TEXT REFERENCES documents(id),
    project_source_id TEXT REFERENCES project_sources(id),
    prior_knowledge TEXT,
    reading_intention TEXT,
    framing_questions TEXT,
    start_page INTEGER,
    end_page INTEGER,
    session_date DATETIME
);

CREATE TABLE IF NOT EXISTS annotations (
    id TEXT PRIMARY KEY,
    document_id TEXT REFERENCES documents(id),
    project_source_id TEXT REFERENCES project_sources(id),
    session_id TEXT REFERENCES reading_sessions(id),
    page_number INTEGER,
    position_json TEXT,
    annotation_type TEXT DEFAULT 'interpretation',
    selected_text TEXT,
    note_content TEXT,
    highlight_color TEXT,
    confidence_level TEXT,
    last_reviewed_at DATETIME,
    created_at DATETIME
);

CREATE TABLE IF NOT EXISTS tags (
    id TEXT PRIMARY KEY,
    label TEXT,
    category TEXT,
    color_hex TEXT
);

CREATE TABLE IF NOT EXISTS annotation_tags (
    annotation_id TEXT REFERENCES annotations(id),
    tag_id TEXT REFERENCES tags(id),
    PRIMARY KEY (annotation_id, tag_id)
);

CREATE TABLE IF NOT EXISTS document_tags (
    document_id TEXT REFERENCES documents(id),
    tag_id TEXT REFERENCES tags(id),
    PRIMARY KEY (document_id, tag_id)
);

CREATE TABLE IF NOT EXISTS annotation_links (
    id TEXT PRIMARY KEY,
    source_annotation_id TEXT REFERENCES annotations(id),
    target_annotation_id TEXT REFERENCES annotations(id),
    rationale TEXT NOT NULL,
    created_at DATETIME
);

CREATE TABLE IF NOT EXISTS review_history (
    id TEXT PRIMARY KEY,
    annotation_id TEXT REFERENCES annotations(id),
    result TEXT,
    interval_days INTEGER,
    reviewed_at DATETIME
);

CREATE TABLE IF NOT EXISTS ai_outputs (
    id TEXT PRIMARY KEY,
    document_id TEXT REFERENCES documents(id),
    project_source_id TEXT REFERENCES project_sources(id),
    annotation_id TEXT REFERENCES annotations(id),
    output_type TEXT,
    content_json TEXT,
    created_at DATETIME
);

CREATE TABLE IF NOT EXISTS review_projects (
    id TEXT PRIMARY KEY,
    title TEXT,
    research_question TEXT,
    structure_json TEXT,
    created_at DATETIME,
    updated_at DATETIME
);

CREATE TABLE IF NOT EXISTS writing_projects (
    id TEXT PRIMARY KEY,
    title TEXT,
    type TEXT,
    status TEXT,
    due_date DATETIME,
    created_at DATETIME,
    updated_at DATETIME
);

CREATE TABLE IF NOT EXISTS annotation_writing_projects (
    annotation_id TEXT REFERENCES annotations(id),
    project_id TEXT REFERENCES writing_projects(id),
    PRIMARY KEY (annotation_id, project_id)
);

CREATE TABLE IF NOT EXISTS review_project_documents (
    project_id TEXT REFERENCES review_projects(id),
    document_id TEXT REFERENCES documents(id),
    PRIMARY KEY (project_id, document_id)
);

CREATE TABLE IF NOT EXISTS progressive_summaries (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES reading_sessions(id),
    document_id TEXT REFERENCES documents(id),
    project_source_id TEXT REFERENCES project_sources(id),
    page_number INTEGER,
    paragraph_index INTEGER,
    paragraph_sentence TEXT,
    rolling_summary TEXT,
    ai_paragraph_sentence TEXT,
    created_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_progressive_summaries_session
    ON progressive_summaries(session_id, page_number, paragraph_index);
CREATE INDEX IF NOT EXISTS idx_progressive_summaries_document
    ON progressive_summaries(document_id);
CREATE INDEX IF NOT EXISTS idx_progressive_summaries_project_source
    ON progressive_summaries(project_source_id);
CREATE INDEX IF NOT EXISTS idx_sources_file_path ON sources(file_path);
CREATE INDEX IF NOT EXISTS idx_project_sources_project ON project_sources(project_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_project_sources_source ON project_sources(source_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_project_sources_project_legacy
    ON project_sources(project_id, legacy_document_id);

CREATE TABLE IF NOT EXISTS contradictions (
    id TEXT PRIMARY KEY,
    annotation_id_a TEXT REFERENCES annotations(id),
    annotation_id_b TEXT REFERENCES annotations(id),
    concept_label TEXT,
    resolution_status TEXT,
    resolution_note TEXT,
    created_at DATETIME
);

CREATE TABLE IF NOT EXISTS concept_nodes (
    id TEXT PRIMARY KEY,
    label TEXT,
    description TEXT,
    source_type TEXT,
    source_id TEXT,
    created_at DATETIME
);

CREATE TABLE IF NOT EXISTS concept_edges (
    id TEXT PRIMARY KEY,
    source_node_id TEXT REFERENCES concept_nodes(id),
    target_node_id TEXT REFERENCES concept_nodes(id),
    relationship_label TEXT,
    rationale TEXT,
    created_at DATETIME
);

CREATE TABLE IF NOT EXISTS reading_events (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES reading_sessions(id),
    document_id TEXT REFERENCES documents(id),
    project_source_id TEXT REFERENCES project_sources(id),
    page_number INTEGER,
    viewed_at DATETIME,
    duration_seconds INTEGER
);

CREATE INDEX IF NOT EXISTS idx_annotations_document_page ON annotations(document_id, page_number);
CREATE INDEX IF NOT EXISTS idx_annotations_project_source_page ON annotations(project_source_id, page_number);
CREATE INDEX IF NOT EXISTS idx_annotations_confidence ON annotations(confidence_level, last_reviewed_at);
CREATE INDEX IF NOT EXISTS idx_annotation_links_source ON annotation_links(source_annotation_id);
CREATE INDEX IF NOT EXISTS idx_annotation_links_target ON annotation_links(target_annotation_id);
CREATE INDEX IF NOT EXISTS idx_annotation_tags_tag ON annotation_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_review_history_annotation ON review_history(annotation_id, reviewed_at);
CREATE INDEX IF NOT EXISTS idx_ai_outputs_document ON ai_outputs(document_id, output_type);
CREATE INDEX IF NOT EXISTS idx_ai_outputs_project_source ON ai_outputs(project_source_id, output_type);
CREATE INDEX IF NOT EXISTS idx_reading_events_session ON reading_events(session_id, viewed_at);
CREATE INDEX IF NOT EXISTS idx_reading_events_document ON reading_events(document_id, page_number);
CREATE INDEX IF NOT EXISTS idx_reading_events_project_source ON reading_events(project_source_id, page_number);
CREATE INDEX IF NOT EXISTS idx_annotation_writing_projects_project ON annotation_writing_projects(project_id);
CREATE INDEX IF NOT EXISTS idx_contradictions_status ON contradictions(resolution_status);
CREATE INDEX IF NOT EXISTS idx_concept_edges_source ON concept_edges(source_node_id);
CREATE INDEX IF NOT EXISTS idx_concept_edges_target ON concept_edges(target_node_id);
