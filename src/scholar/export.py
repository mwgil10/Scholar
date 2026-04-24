import json
import os
import re
import sqlite3
from typing import Optional


TYPE_LABELS = {
    "quote": "Direct Quote",
    "paraphrase": "Paraphrase",
    "interpretation": "Interpretation",
    "synthesis": "Synthesis",
}


def _clean_sentence(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return ""
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def _combine_sentences(parts: list[str], max_sentences: int = 4) -> str:
    cleaned = []
    seen = set()
    for part in parts:
        sentence = _clean_sentence(part)
        if not sentence:
            continue
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(sentence)
        if len(cleaned) >= max_sentences:
            break
    return " ".join(cleaned)


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", (value or "").strip()).strip("-").lower()
    return normalized or "export"


def _load_citation_metadata(raw_value: Optional[str]) -> dict:
    if not raw_value:
        return {}
    try:
        return json.loads(raw_value)
    except Exception:
        return {}


def _citation_line(title: str, citation_metadata: dict) -> str:
    authors = citation_metadata.get("authors") or citation_metadata.get("author") or ""
    year = citation_metadata.get("year") or "n.d."
    source = citation_metadata.get("journal") or citation_metadata.get("source") or citation_metadata.get("publisher") or ""
    volume = citation_metadata.get("volume") or ""
    issue = citation_metadata.get("issue") or ""
    pages = citation_metadata.get("pages") or ""
    doi = citation_metadata.get("doi") or ""
    url = citation_metadata.get("url") or ""

    parts = []
    if authors:
        parts.append(f"{authors} ({year}).")
    else:
        parts.append(f"({year}).")
    parts.append(f"{title}.")
    if source:
        source_part = source
        if volume:
            source_part += f", {volume}"
            if issue:
                source_part += f"({issue})"
        if pages:
            source_part += f", {pages}"
        parts.append(source_part + ".")
    if doi:
        parts.append(f"DOI: {doi}")
    elif url:
        parts.append(url)
    return " ".join(part.strip() for part in parts if part and part.strip())


def _annotated_bib_citation_line(title: str, citation_metadata: dict) -> str:
    line = _citation_line(title, citation_metadata)
    if not line:
        return title
    return line


def _load_document_context(conn: sqlite3.Connection, document_id: Optional[str], project_source_id: Optional[str]) -> dict:
    if project_source_id:
        row = conn.execute(
            """
            SELECT
                ps.id,
                d.id,
                COALESCE(ps.display_title, d.title, s.canonical_title, 'Untitled document'),
                COALESCE(d.file_path, s.file_path, ''),
                COALESCE(ps.status, 'new'),
                COALESCE(ps.priority, 3),
                COALESCE(ps.reading_type, d.reading_type, ''),
                COALESCE(s.citation_metadata, d.citation_metadata, ''),
                COALESCE(rp.title, '')
            FROM project_sources ps
            LEFT JOIN documents d ON d.id = ps.legacy_document_id
            LEFT JOIN sources s ON s.id = ps.source_id
            LEFT JOIN review_projects rp ON rp.id = ps.project_id
            WHERE ps.id = ?
            """,
            (project_source_id,),
        ).fetchone()
        if row:
            return {
                "project_source_id": row[0],
                "document_id": row[1],
                "title": row[2],
                "file_path": row[3],
                "status": row[4],
                "priority": row[5],
                "reading_type": row[6],
                "citation_metadata": _load_citation_metadata(row[7]),
                "project_title": row[8],
            }

    if document_id:
        row = conn.execute(
            """
            SELECT id, COALESCE(title, 'Untitled document'), COALESCE(file_path, ''),
                   COALESCE(status, 'new'), COALESCE(priority, 3),
                   COALESCE(reading_type, ''), COALESCE(citation_metadata, '')
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()
        if row:
            return {
                "project_source_id": None,
                "document_id": row[0],
                "title": row[1],
                "file_path": row[2],
                "status": row[3],
                "priority": row[4],
                "reading_type": row[5],
                "citation_metadata": _load_citation_metadata(row[6]),
                "project_title": "",
            }
    raise ValueError("Could not resolve the requested document context.")


def _load_document_annotations(conn: sqlite3.Connection, document_id: Optional[str], project_source_id: Optional[str]) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            a.id,
            COALESCE(a.annotation_type, 'interpretation'),
            COALESCE(a.selected_text, ''),
            COALESCE(a.note_content, ''),
            COALESCE(a.confidence_level, 'medium'),
            COALESCE(a.page_number, 0),
            COALESCE(a.created_at, ''),
            (
                SELECT wp.title
                FROM annotation_writing_projects awp
                JOIN writing_projects wp ON wp.id = awp.project_id
                WHERE awp.annotation_id = a.id
                ORDER BY wp.updated_at DESC, wp.created_at DESC
                LIMIT 1
            ) AS writing_project_title,
            (
                SELECT ao.content_json
                FROM ai_outputs ao
                WHERE ao.annotation_id = a.id AND ao.output_type = 'explanation'
                ORDER BY ao.created_at DESC
                LIMIT 1
            ) AS latest_ai_output
        FROM annotations a
        WHERE (
            a.project_source_id = ?
            OR (a.project_source_id IS NULL AND a.document_id = ?)
        )
        ORDER BY a.page_number ASC, a.created_at ASC
        """,
        (project_source_id, document_id),
    ).fetchall()

    annotations = []
    for row in rows:
        ai_payload = {}
        if row[8]:
            try:
                ai_payload = json.loads(row[8])
            except Exception:
                ai_payload = {}
        annotations.append(
            {
                "id": row[0],
                "annotation_type": row[1],
                "selected_text": row[2],
                "note_content": row[3],
                "confidence_level": row[4],
                "page_number": row[5],
                "created_at": row[6],
                "writing_project_title": row[7] or "",
                "ai_explanation": ai_payload.get("explanation", ""),
            }
        )
    return annotations


def _render_annotation_block(annotation: dict) -> list[str]:
    annotation_type = annotation["annotation_type"]
    lines = [
        f"### {TYPE_LABELS.get(annotation_type, 'Interpretation')} | Page {annotation['page_number'] + 1} | Confidence: {annotation['confidence_level']}",
    ]
    if annotation["writing_project_title"]:
        lines.append(f"Notebook: {annotation['writing_project_title']}")
    if annotation["selected_text"]:
        lines.append("Selected text:")
        lines.append(f"> {annotation['selected_text']}")
    if annotation["note_content"]:
        label = "Note"
        if annotation_type == "paraphrase":
            label = "Paraphrase"
        elif annotation_type == "interpretation":
            label = "Interpretation"
        elif annotation_type == "synthesis":
            label = "Synthesis"
        lines.append(f"{label}:")
        lines.append(annotation["note_content"])
    if annotation["ai_explanation"]:
        lines.append("AI explanation:")
        lines.append(annotation["ai_explanation"])
    return lines


def _load_latest_summary(conn: sqlite3.Connection, document_id: Optional[str], project_source_id: Optional[str]) -> str:
    row = conn.execute(
        """
        SELECT rolling_summary
        FROM progressive_summaries
        WHERE (
            project_source_id = ?
            OR (project_source_id IS NULL AND document_id = ?)
        ) AND COALESCE(TRIM(rolling_summary), '') <> ''
        ORDER BY page_number DESC, paragraph_index DESC, created_at DESC
        LIMIT 1
        """,
        (project_source_id, document_id),
    ).fetchone()
    return row[0].strip() if row and row[0] else ""


def _build_summary_paragraph(summary_text: str, annotations: list[dict]) -> str:
    if summary_text:
        return _clean_sentence(summary_text)
    candidates = []
    for annotation in annotations:
        if annotation["annotation_type"] == "paraphrase" and annotation["note_content"]:
            candidates.append(annotation["note_content"])
        elif annotation["annotation_type"] == "quote" and annotation["selected_text"]:
            candidates.append(annotation["selected_text"])
    return _combine_sentences(candidates, max_sentences=4) or "No summary notes available yet."


def _build_evaluation_paragraph(annotations: list[dict]) -> str:
    candidates = []
    for annotation in annotations:
        if annotation["annotation_type"] in {"interpretation", "synthesis"} and annotation["note_content"]:
            candidates.append(annotation["note_content"])
    if not candidates:
        for annotation in annotations:
            if annotation["annotation_type"] == "paraphrase" and annotation["note_content"]:
                candidates.append(annotation["note_content"])
    return _combine_sentences(candidates, max_sentences=4) or "No evaluative notes available yet."


def render_annotated_bibliography(db_path: str, review_project_id: str) -> tuple[str, str]:
    with sqlite3.connect(db_path) as conn:
        project_row = conn.execute(
            """
            SELECT id, COALESCE(title, 'Untitled project'), COALESCE(research_question, '')
            FROM review_projects
            WHERE id = ?
            """,
            (review_project_id,),
        ).fetchone()
        if not project_row:
            raise ValueError("Could not find the selected project space.")

        source_rows = conn.execute(
            """
            SELECT
                ps.id,
                d.id,
                COALESCE(ps.display_title, d.title, s.canonical_title, 'Untitled document'),
                COALESCE(s.citation_metadata, d.citation_metadata, ''),
                COALESCE(ps.status, 'new'),
                COALESCE(ps.priority, 3),
                COALESCE(ps.reading_type, d.reading_type, '')
            FROM project_sources ps
            LEFT JOIN documents d ON d.id = ps.legacy_document_id
            LEFT JOIN sources s ON s.id = ps.source_id
            WHERE ps.project_id = ?
            ORDER BY COALESCE(ps.display_title, d.title, s.canonical_title, '') ASC
            """,
            (review_project_id,),
        ).fetchall()

        entries = []
        for row in source_rows:
            project_source_id, document_id, title, citation_raw, status, priority, reading_type = row
            citation_metadata = _load_citation_metadata(citation_raw)
            annotations = _load_document_annotations(conn, document_id, project_source_id)
            summary_text = _load_latest_summary(conn, document_id, project_source_id)
            entries.append(
                {
                    "title": title,
                    "citation_line": _annotated_bib_citation_line(title, citation_metadata),
                    "summary_paragraph": _build_summary_paragraph(summary_text, annotations),
                    "evaluation_paragraph": _build_evaluation_paragraph(annotations),
                    "status": status,
                    "priority": priority,
                    "reading_type": reading_type,
                    "annotation_count": len(annotations),
                }
            )

    project_title = project_row[1]
    lines = [
        f"# Annotated Bibliography: {project_title}",
        "",
        f"Project space: {project_title}",
    ]
    if project_row[2]:
        lines.append(f"Research question: {project_row[2]}")
    lines.extend(["", f"Total sources: {len(entries)}", ""])

    if not entries:
        lines.append("No sources are attached to this project yet.")
    else:
        for entry in entries:
            lines.append(f"## {entry['title']}")
            lines.append("")
            lines.append(entry["citation_line"])
            lines.append("")
            lines.append(entry["summary_paragraph"])
            lines.append("")
            lines.append(entry["evaluation_paragraph"])
            lines.append("")
            lines.append(
                f"Status: {entry['status']} | Priority: {entry['priority']} | Reading type: {entry['reading_type'] or 'unspecified'} | Annotations: {entry['annotation_count']}"
            )
            lines.append("")

    filename = f"annotated-bibliography-{_slugify(project_title)}.md"
    return filename, "\n".join(lines).strip() + "\n"


def render_reading_summary(db_path: str, document_id: Optional[str], project_source_id: Optional[str]) -> tuple[str, str]:
    with sqlite3.connect(db_path) as conn:
        context = _load_document_context(conn, document_id, project_source_id)
        annotations = _load_document_annotations(conn, context["document_id"], context["project_source_id"])

    citation_line = _citation_line(context["title"], context["citation_metadata"])
    lines = [
        f"# Reading Summary: {context['title']}",
        "",
        f"Citation: {citation_line or context['title']}",
        f"Status: {context['status']}",
        f"Priority: {context['priority']}",
        f"Reading type: {context['reading_type'] or 'unspecified'}",
    ]
    if context["project_title"]:
        lines.append(f"Project space: {context['project_title']}")
    if context["file_path"]:
        lines.append(f"Source file: {context['file_path']}")
    lines.extend(["", f"Total annotations: {len(annotations)}", ""])

    if not annotations:
        lines.append("No annotations yet.")
    else:
        for annotation in annotations:
            lines.extend(_render_annotation_block(annotation))
            lines.append("")

    filename = f"reading-summary-{_slugify(context['title'])}.md"
    return filename, "\n".join(lines).strip() + "\n"


def render_writing_project_export(db_path: str, writing_project_id: str) -> tuple[str, str]:
    with sqlite3.connect(db_path) as conn:
        project_row = conn.execute(
            """
            SELECT id, title, COALESCE(type, 'general'), COALESCE(status, 'active')
            FROM writing_projects
            WHERE id = ?
            """,
            (writing_project_id,),
        ).fetchone()
        if not project_row:
            raise ValueError("Could not find the selected notebook.")

        rows = conn.execute(
            """
            SELECT
                a.id,
                COALESCE(a.annotation_type, 'interpretation'),
                COALESCE(a.selected_text, ''),
                COALESCE(a.note_content, ''),
                COALESCE(a.confidence_level, 'medium'),
                COALESCE(a.page_number, 0),
                COALESCE(ps.display_title, d.title, s.canonical_title, 'Untitled document'),
                COALESCE(s.citation_metadata, d.citation_metadata, ''),
                COALESCE(rp.title, ''),
                COALESCE(a.created_at, '')
            FROM annotation_writing_projects awp
            JOIN annotations a ON a.id = awp.annotation_id
            LEFT JOIN project_sources ps ON ps.id = a.project_source_id
            LEFT JOIN documents d ON d.id = a.document_id
            LEFT JOIN sources s ON s.id = ps.source_id
            LEFT JOIN review_projects rp ON rp.id = ps.project_id
            WHERE awp.project_id = ?
            ORDER BY
                CASE COALESCE(a.annotation_type, 'interpretation')
                    WHEN 'paraphrase' THEN 0
                    WHEN 'interpretation' THEN 1
                    WHEN 'synthesis' THEN 2
                    WHEN 'quote' THEN 3
                    ELSE 4
                END,
                COALESCE(ps.display_title, d.title, s.canonical_title, ''),
                a.page_number,
                a.created_at
            """,
            (writing_project_id,),
        ).fetchall()

    project_title = project_row[1] or "Untitled notebook"
    grouped: dict[str, list[dict]] = {"paraphrase": [], "interpretation": [], "synthesis": [], "quote": []}
    for row in rows:
        annotation_type = row[1] or "interpretation"
        citation_metadata = _load_citation_metadata(row[7])
        grouped.setdefault(annotation_type, []).append(
            {
                "id": row[0],
                "annotation_type": annotation_type,
                "selected_text": row[2],
                "note_content": row[3],
                "confidence_level": row[4],
                "page_number": row[5],
                "source_title": row[6],
                "citation_line": _citation_line(row[6], citation_metadata),
                "project_space_title": row[8] or "",
                "created_at": row[9],
            }
        )

    lines = [
        f"# Notebook Export: {project_title}",
        "",
        f"Type: {project_row[2]}",
        f"Status: {project_row[3]}",
        f"Linked annotations: {sum(len(items) for items in grouped.values())}",
        "",
    ]

    section_order = ["paraphrase", "interpretation", "synthesis", "quote"]
    for section in section_order:
        annotations = grouped.get(section, [])
        lines.append(f"## {TYPE_LABELS.get(section, section.title())}s")
        lines.append("")
        if not annotations:
            lines.append("None yet.")
            lines.append("")
            continue
        for annotation in annotations:
            lines.append(
                f"### {annotation['source_title']} | Page {annotation['page_number'] + 1} | Confidence: {annotation['confidence_level']}"
            )
            if annotation["project_space_title"]:
                lines.append(f"Project space: {annotation['project_space_title']}")
            if annotation["citation_line"]:
                lines.append(f"Citation: {annotation['citation_line']}")
            if annotation["selected_text"]:
                lines.append("Selected text:")
                lines.append(f"> {annotation['selected_text']}")
            if annotation["note_content"]:
                lines.append("Your note:")
                lines.append(annotation["note_content"])
            lines.append("")

    filename = f"writing-project-export-{_slugify(project_title)}.md"
    return filename, "\n".join(lines).strip() + "\n"


def write_export_file(output_path: str, content: str) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return output_path
