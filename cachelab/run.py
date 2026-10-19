"""Replay local course ZIPs without redistributing their contents."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from time import perf_counter
from zipfile import ZipFile

from .core import Cache, canonical, equivalent, projection


def load_course(path):
    with ZipFile(path) as archive:
        manifests = [n for n in archive.namelist() if n.endswith("/data/sessions.json")]
        if len(manifests) != 1:
            raise ValueError("expected one data/sessions.json")
        prefix = manifests[0].removesuffix("sessions.json")
        sessions = json.loads(archive.read(manifests[0]))
        tasks = {}
        for name in archive.namelist():
            if name.startswith(prefix + "tasks/") and name.endswith(".json"):
                task = json.loads(archive.read(name))
                if task["task_id"] in tasks:
                    raise ValueError("duplicate task id")
                tasks[task["task_id"]] = task
    referenced = [tid for session in sessions for tid in session["task_ids"]]
    if len(set(referenced)) != len(referenced):
        raise ValueError("duplicate task in session manifest")
    missing = sorted(set(referenced) - tasks.keys())
    if missing:
        raise ValueError(f"missing tasks: {missing}")
    discontinuities = []
    for session in sessions:
        previous = None
        for tid in session["task_ids"]:
            task = tasks[tid]
            if previous is not None and canonical(previous) != canonical(task["initial_graph"]):
                discontinuities.append({"session_id": session["session_id"], "task_id": tid})
            previous = task["steps"][-1]["graph"] if task["steps"] else task["initial_graph"]
    audit = {
        "zip_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        "sessions": len(sessions), "task_files": len(tasks),
        "graph_discontinuities": discontinuities,
        "continuity_verified": not discontinuities,
        "referenced_tasks": len(referenced),
        "unreferenced_tasks": sorted(tasks.keys() - set(referenced)),
    }
    return sessions, tasks, audit


def run(sessions, tasks, strategy, k=5, granularity="fine"):
    counts = Counter()
    latency = 0.0
    for session in sessions:
        cache = Cache(strategy, k)  # Cache must never cross independent worlds.
        step_number = 0
        for task_id in session["task_ids"]:
            task = tasks[task_id]
            for state in task["steps"]:
                step_number += 1
                requests = [("location", obj) for obj in task["target_objects"]]
                requests.append(("summary", None))
                for kind, target in requests:
                    gold = (state["gold"]["location"][target] if kind == "location"
                            else state["gold"]["summary_slots"])
                    graph_input = projection(state["graph"], kind, target, granularity)
                    def mock():
                        # Oracle-backed mock, never a real LLM or measured inference.
                        started = perf_counter()
                        value = json.loads(canonical(gold))
                        return value, perf_counter() - started
                    value, reused, elapsed = cache.request(
                        (kind, target), step_number, graph_input, mock)
                    counts["requests"] += 1
                    counts["reuse_events" if reused else "decision_calls"] += 1
                    latency += elapsed
                    if reused:
                        counts["valid_reuse" if equivalent(value, gold) else "stale_reuse"] += 1
                    else:
                        counts["fresh_correct"] += int(equivalent(value, gold))
    reused = counts["reuse_events"]
    return {
        "strategy": strategy, "k": k if strategy == "fixed" else None,
        "granularity": granularity, "backend": "gold_mock",
        **{name: counts[name] for name in (
            "requests", "decision_calls", "reuse_events", "valid_reuse",
            "stale_reuse", "fresh_correct")},
        "valid_reuse_rate": counts["valid_reuse"] / reused if reused else None,
        "stale_reuse_rate": counts["stale_reuse"] / reused if reused else None,
        "mock_compute_seconds": latency, "evaluation_model_calls": 0,
        "real_llm_latency_seconds": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("results/mock.json"))
    args = parser.parse_args()
    sessions, tasks, audit = load_course(args.course_zip)
    results = [run(sessions, tasks, "none")]
    results += [run(sessions, tasks, "fixed", k=k) for k in (3, 5, 10)]
    results += [run(sessions, tasks, "dependency", granularity=g)
                for g in ("fine", "coarse")]
    report = {"status": "MOCK_ONLY_NOT_FINAL", "data_audit": audit, "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # New results only: avoid silently replacing prior experiment evidence.
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
