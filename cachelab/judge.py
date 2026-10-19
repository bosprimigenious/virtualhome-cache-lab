"""Versioned deterministic structured judgement; never calls another model."""
from .core import equivalent

VERSION = "structured-v2-summary-state-set"


def normalize_summary(answer):
    if not isinstance(answer, dict):
        return answer
    normalized = {}
    for key, value in answer.items():
        if isinstance(value, str):
            value = " ".join(value.casefold().split())
            states, separator, room = value.rpartition(" in ")
            if separator:
                value = " ".join(sorted(set(states.split()))) + " in " + room
        normalized[key] = value
    return normalized


def correct(answer, gold, kind):
    if not isinstance(answer, dict):
        return False
    if kind == "summary":
        return equivalent(normalize_summary(answer), normalize_summary(gold))
    return equivalent(answer, gold)
