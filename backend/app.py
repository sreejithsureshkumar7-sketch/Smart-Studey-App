"""
Smart Study App - Flask backend entry point.

Run with:
    python app.py

Serves the frontend (../frontend) as static files AND exposes the JSON API
the frontend JS calls. Everything is namespaced under /api/ except the
static pages themselves.
"""

import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from config import UPLOAD_FOLDER, MAX_CONTENT_LENGTH, allowed_file, DEFAULT_QUIZ_LENGTH
from models.database import (
    init_db,
    save_document,
    get_document,
    get_document_text,
    list_documents,
    save_quiz,
    get_quiz_questions,
    save_quiz_attempt,
    get_topic_stats,
    get_attempt_history,
    save_study_plan,
    get_latest_study_plan,
)
from services.pdf_processor import extract_text_from_pdf
from services.ai_engine import generate_summary, generate_quiz
from services.weak_topic import analyze_weak_topics
from services.study_plan import build_study_plan

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

init_db()


# ---------------------------------------------------------------------------
# Frontend page routes (serves the static HTML/CSS/JS)
# ---------------------------------------------------------------------------

@app.route("/")
def serve_index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# ---------------------------------------------------------------------------
# API: Upload + Summary
# ---------------------------------------------------------------------------

@app.route("/api/upload", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF files are supported"}), 400

    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    try:
        extracted_text = extract_text_from_pdf(filepath)
        if not extracted_text.strip():
            return jsonify({"error": "Could not extract any text from this PDF (is it scanned/image-only?)"}), 422

        summary = generate_summary(extracted_text)
        doc_id = save_document(file.filename, extracted_text, summary)

        return jsonify({
            "message": "Upload successful",
            "doc_id": doc_id,
            "filename": file.filename,
            "summary": summary,
        })
    except Exception as exc:
        return jsonify({"error": f"Processing failed: {exc}"}), 500


@app.route("/api/documents", methods=["GET"])
def api_list_documents():
    return jsonify(list_documents())


@app.route("/api/documents/<int:doc_id>", methods=["GET"])
def api_get_document(doc_id):
    doc = get_document(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    return jsonify({"id": doc["id"], "filename": doc["filename"], "summary": doc["summary"]})


# ---------------------------------------------------------------------------
# API: Quiz
# ---------------------------------------------------------------------------

@app.route("/api/generate-quiz/<int:doc_id>", methods=["GET"])
def api_generate_quiz(doc_id):
    text = get_document_text(doc_id)
    if not text:
        return jsonify({"error": "Document not found"}), 404

    num_questions = request.args.get("count", DEFAULT_QUIZ_LENGTH, type=int)

    try:
        questions = generate_quiz(text, num_questions)
        if not questions:
            return jsonify({"error": "AI could not generate valid quiz questions from this document"}), 502

        quiz_id = save_quiz(doc_id, questions)

        # Never send correct_answer to the client before submission
        safe_questions = get_quiz_questions(quiz_id, include_answers=False)
        return jsonify({"quiz_id": quiz_id, "doc_id": doc_id, "questions": safe_questions})
    except Exception as exc:
        return jsonify({"error": f"Quiz generation failed: {exc}"}), 500


@app.route("/api/submit-quiz", methods=["POST"])
def api_submit_quiz():
    data = request.get_json(force=True)
    quiz_id = data.get("quiz_id")
    doc_id = data.get("doc_id")
    submitted_answers = data.get("answers", [])  # [{question_id, selected}]

    if not quiz_id or not doc_id or not submitted_answers:
        return jsonify({"error": "quiz_id, doc_id and answers are required"}), 400

    correct_lookup = {
        q["id"]: q for q in get_quiz_questions(quiz_id, include_answers=True)
    }

    enriched = []
    for ans in submitted_answers:
        qid = ans.get("question_id")
        ref = correct_lookup.get(qid)
        if not ref:
            continue
        enriched.append({
            "question_id": qid,
            "selected": ans.get("selected"),
            "correct": ref["correct_answer"],
            "topic": ref["topic"],
        })

    result = save_quiz_attempt(quiz_id, doc_id, enriched)

    # Per-question feedback for immediate display
    feedback = [
        {
            "question_id": a["question_id"],
            "topic": a["topic"],
            "selected": a["selected"],
            "correct": a["correct"],
            "is_correct": a["selected"] == a["correct"],
        }
        for a in enriched
    ]

    return jsonify({**result, "feedback": feedback})


# ---------------------------------------------------------------------------
# API: Weak topics + Dashboard
# ---------------------------------------------------------------------------

@app.route("/api/weak-topics/<int:doc_id>", methods=["GET"])
def api_weak_topics(doc_id):
    stats = get_topic_stats(doc_id)
    if not stats:
        return jsonify({"weak": [], "strong": [], "overall_accuracy": 0.0, "message": "No quiz attempts yet"})
    return jsonify(analyze_weak_topics(stats))


@app.route("/api/dashboard/<int:doc_id>", methods=["GET"])
def api_dashboard(doc_id):
    doc = get_document(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    stats = get_topic_stats(doc_id)
    analysis = analyze_weak_topics(stats) if stats else {"weak": [], "strong": [], "overall_accuracy": 0.0}
    history = get_attempt_history(doc_id)

    return jsonify({
        "document": {"id": doc["id"], "filename": doc["filename"]},
        "topic_stats": stats,
        "analysis": analysis,
        "attempt_history": history,
    })


# ---------------------------------------------------------------------------
# API: Study Plan
# ---------------------------------------------------------------------------

@app.route("/api/study-plan/<int:doc_id>", methods=["POST"])
def api_study_plan(doc_id):
    data = request.get_json(force=True) or {}
    exam_date = data.get("exam_date")  # 'YYYY-MM-DD' or None

    stats = get_topic_stats(doc_id)
    analysis = analyze_weak_topics(stats) if stats else {"weak": []}

    try:
        plan = build_study_plan(analysis["weak"], exam_date)
        save_study_plan(doc_id, exam_date, plan)
        return jsonify(plan)
    except Exception as exc:
        return jsonify({"error": f"Study plan generation failed: {exc}"}), 500


@app.route("/api/study-plan/<int:doc_id>", methods=["GET"])
def api_get_study_plan(doc_id):
    plan = get_latest_study_plan(doc_id)
    if not plan:
        return jsonify({"error": "No study plan generated yet"}), 404
    return jsonify(plan)


# ---------------------------------------------------------------------------

@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "File too large (max 20MB)"}), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=port)
