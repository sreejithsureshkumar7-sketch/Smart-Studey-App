"""
SQLite data layer for the Smart Study App.

Tables
------
documents       -> one row per uploaded PDF
quizzes         -> one row per generated quiz (tied to a document)
quiz_questions  -> individual MCQ questions belonging to a quiz
quiz_attempts   -> one row each time a student submits a quiz
quiz_answers    -> per-question answer log for an attempt (used for weak-topic stats)
study_plans     -> generated study plans tied to a document + exam date
"""

import sqlite3
import json
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            content TEXT NOT NULL,
            summary TEXT,
            uploaded_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (doc_id) REFERENCES documents (id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            options TEXT NOT NULL,      -- JSON encoded list
            correct_answer TEXT NOT NULL,
            topic TEXT NOT NULL,
            FOREIGN KEY (quiz_id) REFERENCES quizzes (id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            doc_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            submitted_at TEXT NOT NULL,
            FOREIGN KEY (quiz_id) REFERENCES quizzes (id) ON DELETE CASCADE,
            FOREIGN KEY (doc_id) REFERENCES documents (id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS quiz_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER NOT NULL,
            question_id INTEGER,
            topic TEXT NOT NULL,
            selected_answer TEXT,
            correct_answer TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            FOREIGN KEY (attempt_id) REFERENCES quiz_attempts (id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS study_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            exam_date TEXT,
            plan_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (doc_id) REFERENCES documents (id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def save_document(filename, content, summary):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO documents (filename, content, summary, uploaded_at) VALUES (?,?,?,?)",
        (filename, content, summary, datetime.utcnow().isoformat()),
    )
    conn.commit()
    doc_id = c.lastrowid
    conn.close()
    return doc_id


def get_document(doc_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_document_text(doc_id):
    doc = get_document(doc_id)
    return doc["content"] if doc else None


def list_documents():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, filename, summary, uploaded_at FROM documents ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Quizzes / Questions
# ---------------------------------------------------------------------------

def save_quiz(doc_id, questions):
    """questions: list of dicts {question, options, answer, topic}"""
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO quizzes (doc_id, created_at) VALUES (?,?)",
        (doc_id, datetime.utcnow().isoformat()),
    )
    quiz_id = c.lastrowid

    for q in questions:
        c.execute(
            """INSERT INTO quiz_questions (quiz_id, question, options, correct_answer, topic)
               VALUES (?,?,?,?,?)""",
            (quiz_id, q["question"], json.dumps(q["options"]), q["answer"], q.get("topic", "General")),
        )
    conn.commit()
    conn.close()
    return quiz_id


def get_quiz_questions(quiz_id, include_answers=False):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM quiz_questions WHERE quiz_id=?", (quiz_id,)
    ).fetchall()
    conn.close()

    questions = []
    for r in rows:
        q = {
            "id": r["id"],
            "question": r["question"],
            "options": json.loads(r["options"]),
            "topic": r["topic"],
        }
        if include_answers:
            q["correct_answer"] = r["correct_answer"]
        questions.append(q)
    return questions


# ---------------------------------------------------------------------------
# Attempts / Answers (used for weak topic detection)
# ---------------------------------------------------------------------------

def save_quiz_attempt(quiz_id, doc_id, answers):
    """
    answers: list of dicts {question_id, selected, topic, correct}
    Returns the attempt summary including per-topic breakdown.
    """
    conn = get_conn()
    c = conn.cursor()

    score = sum(1 for a in answers if a["selected"] == a["correct"])
    total = len(answers)

    c.execute(
        "INSERT INTO quiz_attempts (quiz_id, doc_id, score, total, submitted_at) VALUES (?,?,?,?,?)",
        (quiz_id, doc_id, score, total, datetime.utcnow().isoformat()),
    )
    attempt_id = c.lastrowid

    for a in answers:
        is_correct = 1 if a["selected"] == a["correct"] else 0
        c.execute(
            """INSERT INTO quiz_answers
               (attempt_id, question_id, topic, selected_answer, correct_answer, is_correct)
               VALUES (?,?,?,?,?,?)""",
            (attempt_id, a.get("question_id"), a["topic"], a.get("selected"), a["correct"], is_correct),
        )

    conn.commit()
    conn.close()
    return {"attempt_id": attempt_id, "score": score, "total": total}


def get_topic_stats(doc_id):
    """
    Aggregate correctness per topic across ALL attempts for a document.
    Returns: { topic: {"correct": int, "total": int, "accuracy": float} }
    """
    conn = get_conn()
    rows = conn.execute(
        """SELECT qa.topic, qa.is_correct
           FROM quiz_answers qa
           JOIN quiz_attempts att ON qa.attempt_id = att.id
           WHERE att.doc_id = ?""",
        (doc_id,),
    ).fetchall()
    conn.close()

    stats = {}
    for r in rows:
        t = r["topic"]
        stats.setdefault(t, {"correct": 0, "total": 0})
        stats[t]["total"] += 1
        stats[t]["correct"] += r["is_correct"]

    for t, v in stats.items():
        v["accuracy"] = round((v["correct"] / v["total"]) * 100, 1) if v["total"] else 0.0

    return stats


def get_attempt_history(doc_id):
    conn = get_conn()
    rows = conn.execute(
        """SELECT id, score, total, submitted_at FROM quiz_attempts
           WHERE doc_id=? ORDER BY submitted_at ASC""",
        (doc_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Study plans
# ---------------------------------------------------------------------------

def save_study_plan(doc_id, exam_date, plan):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO study_plans (doc_id, exam_date, plan_json, created_at) VALUES (?,?,?,?)",
        (doc_id, exam_date, json.dumps(plan), datetime.utcnow().isoformat()),
    )
    conn.commit()
    plan_id = c.lastrowid
    conn.close()
    return plan_id


def get_latest_study_plan(doc_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM study_plans WHERE doc_id=? ORDER BY id DESC LIMIT 1",
        (doc_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["plan"] = json.loads(d.pop("plan_json"))
    return d
