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

CREATE INDEX IF NOT EXISTS idx_source_inclusion_source_id
    ON source_inclusion(source_id);
CREATE INDEX IF NOT EXISTS idx_source_inclusion_project_id
    ON source_inclusion(project_id);
CREATE INDEX IF NOT EXISTS idx_source_inclusion_status
    ON source_inclusion(inclusion_status);
