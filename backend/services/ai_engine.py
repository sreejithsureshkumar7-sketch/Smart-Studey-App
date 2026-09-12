"""
All LLM calls live here. Every function returns plain Python data
(str / list / dict) so routes never have to deal with raw API responses.
"""

import json
import re
import sys
import os

import anthropic

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ANTHROPIC_API_KEY, AI_MODEL, DEFAULT_QUIZ_LENGTH

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

MAX_INPUT_CHARS = 12000  # keep prompts within a safe token budget


def _extract_json(raw: str):
    """LLMs sometimes wrap JSON in markdown fences or add stray text - strip it."""
    raw = raw.strip()
    raw = re.sub(r"^```(json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()

    # Fallback: grab the widest {...} or [...] block if extra prose slipped in
    if not (raw.startswith("{") or raw.startswith("[")):
        match = re.search(r"(\[.*\]|\{.*\})", raw, re.DOTALL)
        if match:
            raw = match.group(1)

    return json.loads(raw)


def generate_summary(text: str) -> str:
    """Turn raw notes into short, exam-friendly bullet notes."""
    prompt = f"""You are a study assistant. Convert the following notes into short,
easy-to-understand study notes for a student. Use clear headings and bullet points.
Keep it concise but cover every important concept. Do not invent facts not in the text.

NOTES:
{text[:MAX_INPUT_CHARS]}
"""
    response = client.messages.create(
        model=AI_MODEL,
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def generate_quiz(text: str, num_questions: int = DEFAULT_QUIZ_LENGTH) -> list:
    """
    Generate MCQ questions tagged with a topic name, so answers can later be
    grouped for weak-topic detection.

    Returns: [{"question", "options": [...], "answer", "topic"}, ...]
    """
    prompt = f"""Based on the study material below, write exactly {num_questions}
multiple choice questions that test understanding of the KEY concepts.

Rules:
- Each question needs exactly 4 options.
- "answer" must exactly match one of the strings in "options".
- "topic" should be a short 1-4 word label naming the sub-topic the question
  belongs to (e.g. "Newton's Laws", "Photosynthesis", "SQL Joins"), so
  related questions share the same topic string.
- Return ONLY valid JSON. No markdown fences, no commentary, no extra text.

Format:
[
  {{"question": "...", "options": ["...", "...", "...", "..."], "answer": "...", "topic": "..."}}
]

STUDY MATERIAL:
{text[:MAX_INPUT_CHARS]}
"""
    response = client.messages.create(
        model=AI_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text
    quiz = _extract_json(raw)

    # Basic validation / cleanup
    cleaned = []
    for q in quiz:
        if all(k in q for k in ("question", "options", "answer", "topic")) and len(q["options"]) >= 2:
            cleaned.append(q)
    return cleaned


def generate_study_plan(weak_topics: list, exam_date: str, days_available: int) -> dict:
    """
    weak_topics: list of {"topic": str, "accuracy": float}
    Returns a structured day-by-day plan the frontend can render directly.
    """
    topics_str = "\n".join(f"- {t['topic']} (current accuracy: {t['accuracy']}%)" for t in weak_topics) \
        or "- No weak topics detected yet; focus on general revision."

    prompt = f"""You are a study planner. A student has {days_available} day(s) until
their exam on {exam_date or "an upcoming date"}. Their weakest topics, based on quiz
performance, are:

{topics_str}

Create a personalized day-by-day study plan that prioritizes the weakest topics
first while leaving time for light revision of stronger topics. Return ONLY valid
JSON in this exact shape, no extra commentary:

{{
  "days": [
    {{"day": "Day 1", "focus_topics": ["..."], "tasks": ["...", "..."], "duration_minutes": 60}}
  ],
  "tips": ["...", "..."]
}}
"""
    response = client.messages.create(
        model=AI_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text
    return _extract_json(raw)
