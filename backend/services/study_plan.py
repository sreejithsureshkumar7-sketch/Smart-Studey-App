"""
Wraps AI plan generation with the date-math needed to turn an exam date
into a concrete number of study days.
"""

from datetime import datetime, date
from services.ai_engine import generate_study_plan


def days_until(exam_date_str: str) -> int:
    """exam_date_str is 'YYYY-MM-DD'. Returns at least 1."""
    if not exam_date_str:
        return 7  # sensible default planning window
    try:
        exam_date = datetime.strptime(exam_date_str, "%Y-%m-%d").date()
    except ValueError:
        return 7
    delta = (exam_date - date.today()).days
    return max(delta, 1)


def build_study_plan(weak_topics: list, exam_date: str) -> dict:
    days = days_until(exam_date)
    # Cap the plan length so the LLM doesn't try to plan 90 days in detail
    planning_days = min(days, 14)
    plan = generate_study_plan(weak_topics, exam_date, planning_days)
    plan["days_until_exam"] = days
    return plan
