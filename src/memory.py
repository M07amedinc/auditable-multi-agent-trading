"""Lessons Memory - what the system learned from past mistakes.
Stored as JSON, injected into future agent prompts. Chronological only.
"""
import json, os

class LessonsMemory:
    def __init__(self, path: str = "logs/lessons.json"):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path):
            self.lessons = json.load(open(path))
        else:
            self.lessons = []

    def add(self, lesson: str, conditions: dict, date: str):
        self.lessons.append({"lesson": lesson, "conditions": conditions, "date": date})
        json.dump(self.lessons, open(self.path, "w"), indent=2)

    def relevant(self, conditions: dict, k: int = 5) -> list:
        """Naive retrieval: match on shared condition keys. Swap for embeddings later."""
        scored = []
        for l in self.lessons:
            s = sum(1 for k2, v in conditions.items() if l["conditions"].get(k2) == v)
            scored.append((s, l))
        scored.sort(key=lambda x: -x[0])
        return [l for s, l in scored[:k] if s > 0]

    def advisor_suggestion(self, failures: list) -> str:
        """Mandate Advisor: propose rule changes with evidence (human approves)."""
        # TODO: analyze failure tags, suggest e.g. stop-loss widening
        return "no suggestion"
