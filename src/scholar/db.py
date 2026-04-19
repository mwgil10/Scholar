import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .db_init import DB_PATH, init_db

INCLUSION_STATUSES = {"candidate", "included", "excluded", "deferred"}
RELEVANCE_SCOPES = {"central", "supporting", "methodological", "comparative", "peripheral"}
SCREENING_DEPTHS = {"abstract", "skim", "targeted", "full"}


def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    db_file = DB_PATH if db_path is None else Path(db_path)
    if not db_file.exists():
        init_db(str(db_file))
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now() -> str:
    return datetime.now().isoformat()


def _require_source(conn: sqlite3.Connection, source_id: str):
    row = conn.execute("SELECT id FROM sources WHERE id = ? LIMIT 1", (source_id,)).fetchone()
    if not row:
        raise ValueError(f"Source does not exist: {source_id}")


def _require_project(conn: sqlite3.Connection, project_id: str | None):
    if project_id is None:
        return
    row = conn.execute("SELECT id FROM review_projects WHERE id = ? LIMIT 1", (project_id,)).fetchone()
    if not row:
        raise ValueError(f"Project does not exist: {project_id}")


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def create_inclusion_record(
    source_id: str,
    project_id: str | None = None,
    db_path: str | Path | None = None,
) -> str:
    with _connect(db_path) as conn:
        _require_source(conn, source_id)
        _require_project(conn, project_id)
        if project_id is not None:
            duplicate = conn.execute(
                """
                SELECT id
                FROM source_inclusion
                WHERE source_id = ? AND project_id = ?
                LIMIT 1
                """,
                (source_id, project_id),
            ).fetchone()
            if duplicate:
                raise ValueError(
                    f"Inclusion record already exists for source {source_id} and project {project_id}"
                )
        record_id = str(uuid.uuid4())
        now = _now()
        conn.execute(
            """
            INSERT INTO source_inclusion (
                id, source_id, project_id, inclusion_status, created_at, updated_at
            )
            VALUES (?, ?, ?, 'candidate', ?, ?)
            """,
            (record_id, source_id, project_id, now, now),
        )
        conn.commit()
        return record_id


def get_inclusion_record(
    source_id: str,
    project_id: str | None = None,
    db_path: str | Path | None = None,
) -> dict | None:
    with _connect(db_path) as conn:
        if project_id is None:
            row = conn.execute(
                """
                SELECT *
                FROM source_inclusion
                WHERE source_id = ? AND project_id IS NULL
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (source_id,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT *
                FROM source_inclusion
                WHERE source_id = ? AND project_id = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (source_id, project_id),
            ).fetchone()
        return _row_to_dict(row)


def update_inclusion_status(
    record_id: str,
    status: str,
    reasoning: str | None = None,
    decided_at: str | None = None,
    db_path: str | Path | None = None,
):
    if status not in INCLUSION_STATUSES:
        raise ValueError(f"Invalid inclusion status: {status}")
    reasoning = reasoning.strip() if reasoning is not None else None
    if status in {"included", "excluded"} and not reasoning:
        raise ValueError(f"Inclusion reasoning is required before status can be set to {status}")
    decision_time = decided_at if status in {"included", "excluded"} else None
    if status in {"included", "excluded"} and decision_time is None:
        decision_time = _now()
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM source_inclusion WHERE id = ? LIMIT 1",
            (record_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Inclusion record does not exist: {record_id}")
        conn.execute(
            """
            UPDATE source_inclusion
            SET inclusion_status = ?,
                inclusion_reasoning = COALESCE(?, inclusion_reasoning),
                decided_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (status, reasoning, decision_time, _now(), record_id),
        )
        conn.commit()


def update_inclusion_scope(
    record_id: str,
    relevance_scope: str | None,
    db_path: str | Path | None = None,
):
    if relevance_scope is not None and relevance_scope not in RELEVANCE_SCOPES:
        raise ValueError(f"Invalid relevance scope: {relevance_scope}")
    with _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE source_inclusion
            SET relevance_scope = ?, updated_at = ?
            WHERE id = ?
            """,
            (relevance_scope, _now(), record_id),
        )
        if conn.total_changes == 0:
            raise ValueError(f"Inclusion record does not exist: {record_id}")
        conn.commit()


def update_inclusion_notes(
    record_id: str,
    project_role_note: str | None = None,
    screening_depth: str | None = None,
    db_path: str | Path | None = None,
):
    if screening_depth is not None and screening_depth not in SCREENING_DEPTHS:
        raise ValueError(f"Invalid screening depth: {screening_depth}")
    with _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE source_inclusion
            SET project_role_note = COALESCE(?, project_role_note),
                screening_depth = COALESCE(?, screening_depth),
                updated_at = ?
            WHERE id = ?
            """,
            (project_role_note, screening_depth, _now(), record_id),
        )
        if conn.total_changes == 0:
            raise ValueError(f"Inclusion record does not exist: {record_id}")
        conn.commit()


def _source_inclusion_select(where_sql: str, params: Iterable, db_path: str | Path | None) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT
                s.id AS source_id,
                s.canonical_title AS title,
                s.file_path,
                s.source_url,
                s.citation_metadata,
                si.id AS inclusion_id,
                si.project_id,
                si.inclusion_status,
                si.relevance_scope,
                si.inclusion_reasoning,
                si.project_role_note,
                si.screening_depth,
                si.decided_at,
                si.created_at,
                si.updated_at
            FROM source_inclusion si
            JOIN sources s ON s.id = si.source_id
            {where_sql}
            ORDER BY si.updated_at DESC
            """,
            tuple(params),
        ).fetchall()
        return [dict(row) for row in rows]


def get_staging_pool(db_path: str | Path | None = None) -> list[dict]:
    return _source_inclusion_select(
        """
        WHERE si.project_id IS NULL
          AND si.inclusion_status IN ('candidate', 'included', 'deferred')
        """,
        (),
        db_path,
    )


def get_project_inclusions(project_id: str, db_path: str | Path | None = None) -> list[dict]:
    return _source_inclusion_select(
        """
        WHERE si.project_id = ?
          AND si.inclusion_status = 'included'
        """,
        (project_id,),
        db_path,
    )


def get_inclusions_by_status(
    statuses: Iterable[str],
    project_id: str | None = None,
    db_path: str | Path | None = None,
) -> list[dict]:
    normalized = tuple(statuses)
    invalid = [status for status in normalized if status not in INCLUSION_STATUSES]
    if invalid:
        raise ValueError(f"Invalid inclusion status: {invalid[0]}")
    if not normalized:
        return []
    placeholders = ", ".join("?" for _ in normalized)
    params: list[str] = list(normalized)
    if project_id is None:
        project_filter = "si.project_id IS NULL"
    else:
        project_filter = "si.project_id = ?"
        params.append(project_id)
    return _source_inclusion_select(
        f"""
        WHERE si.inclusion_status IN ({placeholders})
          AND {project_filter}
        """,
        params,
        db_path,
    )


def seed_project_inclusions(
    project_id: str,
    source_ids: Iterable[str],
    db_path: str | Path | None = None,
) -> int:
    unique_source_ids = tuple(dict.fromkeys(source_ids))
    if not unique_source_ids:
        return 0
    with _connect(db_path) as conn:
        _require_project(conn, project_id)
        for source_id in unique_source_ids:
            _require_source(conn, source_id)
            duplicate = conn.execute(
                """
                SELECT id
                FROM source_inclusion
                WHERE source_id = ? AND project_id = ?
                LIMIT 1
                """,
                (source_id, project_id),
            ).fetchone()
            if duplicate:
                raise ValueError(
                    f"Inclusion record already exists for source {source_id} and project {project_id}"
                )
        placeholders = ", ".join("?" for _ in unique_source_ids)
        conn.execute(
            f"""
            UPDATE source_inclusion
            SET project_id = ?, updated_at = ?
            WHERE project_id IS NULL
              AND inclusion_status = 'included'
              AND source_id IN ({placeholders})
            """,
            (project_id, _now(), *unique_source_ids),
        )
        updated = conn.total_changes
        conn.commit()
        return updated


def get_triage_annotations(source_id: str, db_path: str | Path | None = None) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT a.*
            FROM annotations a
            JOIN project_sources ps ON ps.id = a.project_source_id
            WHERE ps.source_id = ?
              AND a.triage = 1
            ORDER BY a.created_at ASC
            """,
            (source_id,),
        ).fetchall()
        return [dict(row) for row in rows]
