"""Stream cache decisions and backend outcomes, independently of grading."""
from copy import deepcopy
import hashlib
import json
from time import perf_counter

from .backend import invoke
from .core import Cache, canonical, projection

STRATEGIES = [
    ("none", "none", 5, "fine"),
    ("fixed-k3", "fixed", 3, "fine"),
    ("fixed-k5", "fixed", 5, "fine"),
    ("fixed-k10", "fixed", 10, "fine"),
    ("dependency-fine", "dependency", 5, "fine"),
    ("dependency-coarse", "dependency", 5, "coarse"),
]


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def stream_strategy(sessions, tasks, audit, specification, backend, boundary_policy, stream):
    strategy_id, strategy, k, granularity = specification
    boundary_tasks = {item["task_id"] for item in audit["graph_discontinuities"]}
    for session in sessions:
        cache = Cache(strategy, k)
        gold_history = {}
        source_history = {}
        stream.write(json.dumps({"event_type": "session_start", "strategy_id": strategy_id,
                                 "session_id": session["session_id"]}) + "\n")
        stream.flush()
        step_number = 0
        for task_id in session["task_ids"]:
            task = tasks[task_id]
            boundary_reset = boundary_policy == "reset" and task_id in boundary_tasks
            if boundary_reset:
                cache.clear()
                gold_history.clear()
                source_history.clear()
                stream.write(json.dumps({"event_type": "boundary_reset", "strategy_id": strategy_id,
                                         "session_id": session["session_id"], "task_id": task_id}) + "\n")
                stream.flush()
            for task_step, state in enumerate(task["steps"], 1):
                step_number += 1
                graph = state["graph"]
                requests = [("location", target) for target in task["target_objects"]] + [("summary", None)]
                for kind, target in requests:
                    request_started = perf_counter()
                    key = (kind, target)
                    gold = (state["gold"]["location"][target] if kind == "location"
                            else state["gold"]["summary_slots"])
                    deps = projection(graph, kind, target, granularity, course_semantics=True)
                    reused, reason, fingerprint = cache.decision(key, step_number, deps)
                    old = cache.entries.get(key)
                    # All strategies send identical full state, independent of dependency granularity.
                    # In particular, never pass gold to the real model backend.
                    model_input = deepcopy(graph)
                    if reused:
                        outcome = {"answer": deepcopy(old[2]), "raw_output": None,
                                   "latency_seconds": 0.0, "error": None, "error_type": None,
                                   "usage": {}, "finish_reason": None}
                    elif backend is None:
                        start = perf_counter()
                        answer = deepcopy(gold)
                        outcome = {"answer": answer, "raw_output": canonical(answer),
                                   "latency_seconds": perf_counter() - start, "error": None,
                                   "error_type": None, "usage": {}, "finish_reason": "mock"}
                    else:
                        outcome = invoke(backend, kind, target, model_input)
                    event_id = digest([strategy_id, session["session_id"], task_id, task_step, kind, target])
                    event = {
                        "event_type": "request", "schema_version": 1, "event_id": event_id,
                        "strategy_id": strategy_id, "strategy": strategy,
                        "granularity": granularity, "backend": "mock" if backend is None else "openai",
                        "session_id": session["session_id"], "task_id": task_id,
                        "session_step": step_number, "task_step": task_step,
                        "kind": kind, "target": target, "reused": reused, "reason": reason,
                        "prior_cache_created_step": old[0] if old is not None else None,
                        "cache_created_step": (old[0] if reused else
                                               step_number if outcome["error"] is None else None),
                        "cache_source_event_id": source_history.get(key) if reused else None,
                        "dependency_sha256": hashlib.sha256(fingerprint.encode()).hexdigest(),
                        "dependencies": deps, "model_input_sha256": digest(model_input),
                        "model_input": None if reused else model_input,
                        "action": state.get("action"), "gold": gold,
                        "had_prior": old is not None,
                        "prior_gold": gold_history.get(key),
                        "prior_answer": old[2] if old is not None else None,
                        **outcome,
                        "request_wall_seconds": perf_counter() - request_started,
                    }
                    stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                    stream.flush()
                    if not reused and outcome["error"] is None and isinstance(outcome["answer"], dict):
                        cache.store(key, step_number, fingerprint, outcome["answer"])
                        source_history[key] = event_id
                        gold_history[key] = deepcopy(gold)
