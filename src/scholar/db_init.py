import sqlite3
import pathlib
import sys
import uuid
from datetime import datetime

SCHEMA_PATH = pathlib.Path(__file__).parent.parent.parent / "schema.sql"
DB_PATH = pathlib.Path(__file__).parent.parent / "scholar.db"
MIGRATIONS_PATH = pathlib.Path(__file__).parent / "migrations"

INCREMENTAL_SCHEMA_SQL = """
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

CREATE INDEX IF NOT EXISTS idx_sources_file_path ON sources(file_path);
CREATE INDEX IF NOT EXISTS idx_project_sources_project ON project_sources(project_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_project_sources_source ON project_sources(source_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_project_sources_project_legacy
    ON project_sources(project_id, legacy_document_id);

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

CREATE INDEX IF NOT EXISTS idx_annotation_writing_projects_project
    ON annotation_writing_projects(project_id);

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

CREATE INDEX IF NOT EXISTS idx_annotation_tags_tag
    ON annotation_tags(tag_id);
"""

SYSTEM_TAGS = [
    ("theory", "system", "#6b8fd6"),
    ("method", "system", "#5b9b7b"),
    ("finding", "system", "#d18a3f"),
    ("limitation", "system", "#c56b6b"),
    ("contradiction", "system", "#9b6bc5"),
    ("definition", "system", "#5d8aa8"),
    ("evidence", "system", "#4f88c6"),
]


def _ensure_default_project(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT id FROM review_projects WHERE title = ? ORDER BY updated_at DESC, created_at DESC LIMIT 1",
        ("General Research",),
    ).fetchone()
    if row:
        return row[0]
    row = conn.execute(
        "SELECT id FROM review_projects ORDER BY updated_at DESC, created_at DESC LIMIT 1"
    ).fetchone()
    if row:
        project_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        conn.execute(
            """
            INSERT INTO review_projects (id, title, research_question, structure_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project_id, "General Research", "", "{}", now, now),
        )
        return project_id
    project_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn.execute(
        """
        INSERT INTO review_projects (id, title, research_question, structure_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (project_id, "General Research", "", "{}", now, now),
    )
    return project_id


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return bool(row)


def _column_names(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, definition: str):
    if column_name in _column_names(conn, table_name):
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _ensure_phase2_columns(conn: sqlite3.Connection):
    _ensure_column(conn, "reading_sessions", "project_source_id", "TEXT REFERENCES project_sources(id)")
    _ensure_column(conn, "annotations", "project_source_id", "TEXT REFERENCES project_sources(id)")
    _ensure_column(conn, "annotations", "annotation_type", "TEXT DEFAULT 'interpretation'")
    _ensure_column(conn, "ai_outputs", "project_source_id", "TEXT REFERENCES project_sources(id)")
    _ensure_column(conn, "progressive_summaries", "project_source_id", "TEXT REFERENCES project_sources(id)")
    _ensure_column(conn, "reading_events", "project_source_id", "TEXT REFERENCES project_sources(id)")


def _ensure_phase2_indexes(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_progressive_summaries_project_source
            ON progressive_summaries(project_source_id);
        CREATE INDEX IF NOT EXISTS idx_annotations_project_source_page
            ON annotations(project_source_id, page_number);
        CREATE INDEX IF NOT EXISTS idx_ai_outputs_project_source
            ON ai_outputs(project_source_id, output_type);
        CREATE INDEX IF NOT EXISTS idx_reading_events_project_source
            ON reading_events(project_source_id, page_number);
        """
    )


def _ensure_incremental_schema(conn: sqlite3.Connection):
    conn.executescript(INCREMENTAL_SCHEMA_SQL)


def _seed_system_tags(conn: sqlite3.Connection):
    existing = {
        (row[0] or "").strip().lower()
        for row in conn.execute("SELECT label FROM tags").fetchall()
    }
    now = datetime.now().isoformat()
    for label, category, color_hex in SYSTEM_TAGS:
        if label.lower() in existing:
            continue
        conn.execute(
            "INSERT INTO tags (id, label, category, color_hex) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), label, category, color_hex),
        )


def _ensure_schema_migrations_table(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at DATETIME NOT NULL
        )
        """
    )


def _migration_files() -> list[pathlib.Path]:
    if not MIGRATIONS_PATH.exists():
        return []
    return sorted(
        path
        for path in MIGRATIONS_PATH.glob("*.sql")
        if path.is_file() and path.name[:3].isdigit()
    )


def _migration_version(path: pathlib.Path) -> str:
    return path.stem.split("_", 1)[0]


def _applied_migration_versions(conn: sqlite3.Connection) -> set[str]:
    _ensure_schema_migrations_table(conn)
    return {
        row[0]
        for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
    }


def apply_migrations(conn: sqlite3.Connection):
    _ensure_schema_migrations_table(conn)
    applied_versions = _applied_migration_versions(conn)
    for path in _migration_files():
        version = _migration_version(path)
        if version in applied_versions:
            continue
        sql = path.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute(
            """
            INSERT INTO schema_migrations (version, name, applied_at)
            VALUES (?, ?, ?)
            """,
            (version, path.name, datetime.now().isoformat()),
        )
        conn.commit()


def migrate_phase1_library(db_path: str = None):
    db_file = DB_PATH if db_path is None else pathlib.Path(db_path)
    with sqlite3.connect(str(db_file)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        _ensure_incremental_schema(conn)
        _seed_system_tags(conn)
        default_project_id = _ensure_default_project(conn)

        memberships = {}
        for project_id, document_id in conn.execute(
            "SELECT project_id, document_id FROM review_project_documents"
        ):
            memberships.setdefault(document_id, set()).add(project_id)

        existing_sources_by_path = {
            (file_path or ""): source_id
            for source_id, file_path in conn.execute(
                "SELECT id, COALESCE(file_path, '') FROM sources"
            )
            if file_path
        }
        existing_sources_by_title = {
            (title or ""): source_id
            for source_id, title in conn.execute(
                "SELECT id, COALESCE(canonical_title, '') FROM sources"
            )
            if title
        }

        rows = conn.execute(
            """
            SELECT id, title, file_path, source_url, reading_type, status, priority,
                   citation_metadata, created_at, updated_at, total_pages
            FROM documents
            ORDER BY updated_at DESC, created_at DESC
            """
        ).fetchall()

        for (
            legacy_document_id,
            title,
            file_path,
            source_url,
            reading_type,
            status,
            priority,
            citation_metadata,
            created_at,
            updated_at,
            _total_pages,
        ) in rows:
            normalized_path = (file_path or "").strip()
            normalized_title = (title or "").strip() or normalized_path or legacy_document_id

            if normalized_path and normalized_path in existing_sources_by_path:
                source_id = existing_sources_by_path[normalized_path]
            elif not normalized_path and normalized_title in existing_sources_by_title:
                source_id = existing_sources_by_title[normalized_title]
            else:
                source_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO sources (
                        id, file_path, canonical_title, source_url, citation_metadata,
                        doc_fingerprint, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        normalized_path or None,
                        normalized_title,
                        source_url,
                        citation_metadata,
                        None,
                        created_at,
                        updated_at,
                    ),
                )
                if normalized_path:
                    existing_sources_by_path[normalized_path] = source_id
                else:
                    existing_sources_by_title[normalized_title] = source_id

            target_projects = memberships.get(legacy_document_id) or {default_project_id}
            for project_id in target_projects:
                existing_project_source = conn.execute(
                    """
                    SELECT id
                    FROM project_sources
                    WHERE project_id = ? AND legacy_document_id = ?
                    """,
                    (project_id, legacy_document_id),
                ).fetchone()
                if existing_project_source:
                    conn.execute(
                        """
                        UPDATE project_sources
                        SET source_id = ?, display_title = ?, status = ?, priority = ?,
                            reading_type = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            source_id,
                            title,
                            status,
                            priority,
                            reading_type,
                            updated_at,
                            existing_project_source[0],
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO project_sources (
                            id, project_id, source_id, legacy_document_id, display_title,
                            status, priority, reading_type, local_notes, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(uuid.uuid4()),
                            project_id,
                            source_id,
                            legacy_document_id,
                            title,
                            status,
                            priority,
                            reading_type,
                            None,
                            created_at,
                            updated_at,
                        ),
                    )
        conn.commit()


def repair_default_project_assignments(db_path: str = None):
    db_file = DB_PATH if db_path is None else pathlib.Path(db_path)
    with sqlite3.connect(str(db_file)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        _ensure_incremental_schema(conn)
        _seed_system_tags(conn)
        default_project_id = _ensure_default_project(conn)
        stray_rows = conn.execute(
            """
            SELECT ps.id, ps.legacy_document_id
            FROM project_sources ps
            LEFT JOIN review_project_documents rpd
                ON rpd.project_id = ps.project_id AND rpd.document_id = ps.legacy_document_id
            WHERE ps.legacy_document_id IS NOT NULL
              AND rpd.document_id IS NULL
              AND ps.project_id <> ?
            """,
            (default_project_id,),
        ).fetchall()
        for project_source_id, legacy_document_id in stray_rows:
            existing_default = conn.execute(
                """
                SELECT id
                FROM project_sources
                WHERE project_id = ? AND legacy_document_id = ?
                LIMIT 1
                """,
                (default_project_id, legacy_document_id),
            ).fetchone()
            if existing_default:
                conn.execute("DELETE FROM project_sources WHERE id = ?", (project_source_id,))
            else:
                conn.execute(
                    "UPDATE project_sources SET project_id = ? WHERE id = ?",
                    (default_project_id, project_source_id),
                )
        conn.commit()


def migrate_phase2_workflows(db_path: str = None):
    db_file = DB_PATH if db_path is None else pathlib.Path(db_path)
    with sqlite3.connect(str(db_file)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        _ensure_incremental_schema(conn)
        _seed_system_tags(conn)
        _ensure_phase2_columns(conn)

        conn.execute(
            """
            UPDATE reading_sessions
            SET project_source_id = (
                SELECT ps.id
                FROM project_sources ps
                WHERE ps.legacy_document_id = reading_sessions.document_id
                ORDER BY ps.updated_at DESC, ps.created_at DESC
                LIMIT 1
            )
            WHERE project_source_id IS NULL AND document_id IS NOT NULL
            """
        )

        conn.execute(
            """
            UPDATE annotations
            SET project_source_id = COALESCE(
                (
                    SELECT rs.project_source_id
                    FROM reading_sessions rs
                    WHERE rs.id = annotations.session_id
                    LIMIT 1
                ),
                (
                    SELECT ps.id
                    FROM project_sources ps
                    WHERE ps.legacy_document_id = annotations.document_id
                    ORDER BY ps.updated_at DESC, ps.created_at DESC
                    LIMIT 1
                )
            )
            WHERE project_source_id IS NULL
            """
        )

        conn.execute(
            """
            UPDATE ai_outputs
            SET project_source_id = COALESCE(
                (
                    SELECT a.project_source_id
                    FROM annotations a
                    WHERE a.id = ai_outputs.annotation_id
                    LIMIT 1
                ),
                (
                    SELECT ps.id
                    FROM project_sources ps
                    WHERE ps.legacy_document_id = ai_outputs.document_id
                    ORDER BY ps.updated_at DESC, ps.created_at DESC
                    LIMIT 1
                )
            )
            WHERE project_source_id IS NULL
            """
        )

        conn.execute(
            """
            UPDATE progressive_summaries
            SET project_source_id = COALESCE(
                (
                    SELECT rs.project_source_id
                    FROM reading_sessions rs
                    WHERE rs.id = progressive_summaries.session_id
                    LIMIT 1
                ),
                (
                    SELECT ps.id
                    FROM project_sources ps
                    WHERE ps.legacy_document_id = progressive_summaries.document_id
                    ORDER BY ps.updated_at DESC, ps.created_at DESC
                    LIMIT 1
                )
            )
            WHERE project_source_id IS NULL
            """
        )

        conn.execute(
            """
            UPDATE reading_events
            SET project_source_id = COALESCE(
                (
                    SELECT rs.project_source_id
                    FROM reading_sessions rs
                    WHERE rs.id = reading_events.session_id
                    LIMIT 1
                ),
                (
                    SELECT ps.id
                    FROM project_sources ps
                    WHERE ps.legacy_document_id = reading_events.document_id
                    ORDER BY ps.updated_at DESC, ps.created_at DESC
                    LIMIT 1
                )
            )
            WHERE project_source_id IS NULL
            """
        )

        _ensure_phase2_indexes(conn)
        conn.execute(
            """
            UPDATE annotations
            SET annotation_type = 'interpretation'
            WHERE annotation_type IS NULL OR TRIM(annotation_type) = ''
            """
        )
        conn.commit()


def init_db(db_path: str = None):
    db_file = DB_PATH if db_path is None else pathlib.Path(db_path)
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema file not found at {SCHEMA_PATH}")
    with sqlite3.connect(str(db_file)) as conn:
        if not _table_exists(conn, "documents"):
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                conn.executescript(f.read())
        else:
            conn.executescript(INCREMENTAL_SCHEMA_SQL)
        _seed_system_tags(conn)
    migrate_phase1_library(str(db_file))
    migrate_phase2_workflows(str(db_file))
    repair_default_project_assignments(str(db_file))
    with sqlite3.connect(str(db_file)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        apply_migrations(conn)
    print(f"Initialized DB at {db_file}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    init_db(path)
