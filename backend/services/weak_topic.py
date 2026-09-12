"""
Turns raw per-topic accuracy stats (from the database) into a ranked
list of weak topics that the study-plan generator and dashboard can use.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import WEAK_TOPIC_THRESHOLD


def analyze_weak_topics(topic_stats: dict) -> dict:
    """
    topic_stats: { topic: {"correct": int, "total": int, "accuracy": float} }

    Returns:
    {
        "weak":     [{"topic", "accuracy", "correct", "total"}, ...]  sorted worst-first,
        "strong":   [...] sorted best-first,
        "overall_accuracy": float
    }
    """
    weak, strong = [], []
    total_correct = total_questions = 0

    for topic, stats in topic_stats.items():
        entry = {
            "topic": topic,
            "accuracy": stats["accuracy"],
            "correct": stats["correct"],
            "total": stats["total"],
        }
        total_correct += stats["correct"]
        total_questions += stats["total"]

        if stats["accuracy"] / 100 < WEAK_TOPIC_THRESHOLD:
            weak.append(entry)
        else:
            strong.append(entry)

    weak.sort(key=lambda x: x["accuracy"])
    strong.sort(key=lambda x: -x["accuracy"])

    overall = round((total_correct / total_questions) * 100, 1) if total_questions else 0.0

    return {"weak": weak, "strong": strong, "overall_accuracy": overall}
