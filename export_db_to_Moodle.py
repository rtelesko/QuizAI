"""
export_db_to_Moodle.py

Exports quiz questions from a Firebase Firestore collection to a Moodle-compatible XML file.

This version is cleaned of CLI logging. Instead, when used inside Streamlit,
it will surface warnings and success messages in the sidebar.
"""

from __future__ import annotations

import argparse
from typing import Iterable, List, Optional
from xml.sax.saxutils import escape

# Try Streamlit for in-app notifications; fall back to no-ops outside Streamlit
try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover
    st = None  # type: ignore

# Firebase
from firebase_admin import firestore
from firebase_backend import initialize_firebase  # provided in your project


def _xml_text(s: str) -> str:
    """Escape text for inclusion inside Moodle <text> elements."""
    if s is None:
        return ""
    return escape(str(s), entities={'"': "&quot;", "'": "&apos;"})


def _iter_questions(collection: str, limit: Optional[int]) -> Iterable[dict]:
    """Stream questions from Firestore."""
    db = firestore.client()
    docs = db.collection(collection).stream()
    count = 0
    for doc in docs:
        q = doc.to_dict() or {}
        if q:  # only yield non-empty records
            yield q
            count += 1
            if limit is not None and count >= limit:
                break


def _validate_question(q: dict) -> Optional[str]:
    """Return None if valid; otherwise a string describing the validation error."""
    required = ["question", "options", "answer"]
    for k in required:
        if k not in q or q[k] in (None, "", []):
            return f"missing required field '{k}'"

    options: List[str] = [str(o) for o in list(q["options"])]
    answer: str = str(q["answer"])

    if answer not in options:
        return "answer is not among options"

    # exactly one correct option
    if sum(1 for o in options if o == answer) != 1:
        return "exactly one option must equal the answer"

    return None


def _question_to_xml(idx: int, q: dict, single: bool = True, shuffleanswers: bool = True) -> str:
    """Convert a single question dict to Moodle XML <question type='multichoice'> string."""
    question = str(q.get("question", "")).strip()
    options = [str(o) for o in q.get("options", [])]
    answer = str(q.get("answer", "")).strip()
    feedback = str(q.get("explanation", "") or "").strip()
    topic = str(q.get("topic", "") or "").strip()

    name_text = f"Q{idx}: {topic}" if topic else f"Q{idx}"

    lines = []
    lines.append('  <question type="multichoice">')
    lines.append(f"    <name><text>{_xml_text(name_text)}</text></name>")
    lines.append('    <questiontext format="html">')
    lines.append(f"      <text>{_xml_text(question)}</text>")
    lines.append("    </questiontext>")
    lines.append("    <generalfeedback>")
    lines.append(f"      <text>{_xml_text(feedback)}</text>")
    lines.append("    </generalfeedback>")
    lines.append("    <defaultgrade>1.0000000</defaultgrade>")
    lines.append("    <penalty>0.0000000</penalty>")
    lines.append(f"    <single>{'true' if single else 'false'}</single>")
    lines.append(f"    <shuffleanswers>{'true' if shuffleanswers else 'false'}</shuffleanswers>")
    lines.append("    <answernumbering>abc</answernumbering>")

    for opt in options:
        fraction = "100" if opt == answer else "0"
        lines.append(f'    <answer fraction="{fraction}" format="html">')
        lines.append(f"      <text>{_xml_text(opt)}</text>")
        lines.append("      <feedback>")
        lines.append(f"        <text>{'Correct.' if fraction == '100' else 'Incorrect.'}</text>")
        lines.append("      </feedback>")
        lines.append("    </answer>")

    lines.append("  </question>")
    return "\n".join(lines)


def export_db_to_Moodle(
    credential_path: str,
    output_path: str,
    collection: str = "quiz_questions",
    *,
    limit: Optional[int] = None,
    category: Optional[str] = None,
    shuffleanswers: bool = True
) -> int:
    """
    Export Firestore quiz questions to a Moodle XML file.

    Returns:
        The number of questions successfully written.
    """
    # Initialize Firebase
    initialize_firebase(credential_path)

    # Build XML
    parts: List[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append("<quiz>")

    # Optional category (Moodle uses a special 'category' question to set the context)
    if category:
        parts.append('  <question type="category">')
        parts.append("    <category>")
        parts.append(f"      <text>$course$/{_xml_text(category)}</text>")
        parts.append("    </category>")
        parts.append("  </question>")

    written = 0
    for idx, q in enumerate(_iter_questions(collection, limit=limit), start=1):
        err = _validate_question(q)
        if err:
            if st is not None:
                st.sidebar.warning(f"Skipping invalid question {idx}: {err}")
            # silently skip outside Streamlit
            continue

        parts.append(_question_to_xml(idx, q, single=True, shuffleanswers=shuffleanswers))
        written += 1

    parts.append("</quiz>")

    # Write the file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))

    # Success message in Streamlit sidebar (silent in CLI usage)
    if st is not None:
        st.sidebar.success(f"Exported {written} questions to {output_path}")

    return written


def _parse_args() -> argparse.Namespace:  # CLI remains supported, but silent
    p = argparse.ArgumentParser(description="Export Firestore quiz questions to Moodle XML")
    p.add_argument("credential_path", help="Path to the Firebase service account JSON")
    p.add_argument("output_path", help="Destination Moodle XML file")
    p.add_argument("--collection", default="quiz_questions", help="Firestore collection name (default: quiz_questions)")
    p.add_argument("--limit", type=int, default=None, help="Max number of questions to export")
    p.add_argument("--category", type=str, default=None, help="Optional Moodle category path under $course$")
    p.add_argument("--no-shuffle", action="store_true", help="Disable answer shuffling in Moodle")
    return p.parse_args()


if __name__ == "__main__":  # pragma: no cover
    args = _parse_args()
    export_db_to_Moodle(
        credential_path=args.credential_path,
        output_path=args.output_path,
        collection=args.collection,
        limit=args.limit,
        category=args.category,
        shuffleanswers=(not args.no_shuffle),
    )
