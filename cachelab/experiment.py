"""Run six controlled strategies with streamed, replayable evidence."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter

from .replay import STRATEGIES, stream_strategy
from .evaluate import evaluate
from .judge import VERSION
from .evidence import build_manifest
from .replay import digest
from .run import load_course

def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def select(sessions, tasks, session_limit=None, task_limit=None):
    if (session_limit is not None and session_limit < 1) or (task_limit is not None and task_limit < 1):
        raise ValueError("limits must be positive")
    sessions = deepcopy(sessions[:session_limit])
    for session in sessions:
        session["task_ids"] = session["task_ids"][:task_limit]
    if not sessions or not any(s["task_ids"] for s in sessions):
        raise ValueError("empty experiment selection")
    expected = sum((len(tasks[tid]["target_objects"]) + 1) * len(tasks[tid]["steps"])
                   for session in sessions for tid in session["task_ids"])
    if not expected:
        raise ValueError("selection has no requests")
    return sessions, expected


def execute(course_zip, output_dir, backend=None, session_limit=None, task_limit=None,
            boundary_policy="reset"):
    if boundary_policy not in {"reset", "preserve"}:
        raise ValueError("invalid boundary policy")
    sessions, tasks, audit = load_course(course_zip)
    selected, expected = select(sessions, tasks, session_limit, task_limit)
    output_dir = Path(output_dir)
    # Reserve the evidence directory before any model call. Existing runs are immutable.
    output_dir.mkdir(parents=True, exist_ok=False)
    config = {
        "schema_version": 1,
        "request_manifest": build_manifest(selected, tasks), "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "backend": "mock" if backend is None else "openai", "judge_version": VERSION,
        "strategies": [spec[0] for spec in STRATEGIES], "boundary_policy": boundary_policy,
        "selected_sessions": selected, "expected_requests_per_strategy": expected,
        "model": backend.configuration() if backend is not None else {"name": "gold_mock"},
        "dependency_protocol": "course-v1-edge-order-bidirectional-in",
        "scope": "full_manifest" if session_limit is None and task_limit is None else "limited_smoke",
    }
    write_new(output_dir / "config.json", config)
    write_new(output_dir / "data-audit.json", audit)
    started = perf_counter()
    try:
        with (output_dir / "events.jsonl").open("x", encoding="utf-8") as stream:
            for specification in STRATEGIES:
                stream_strategy(selected, tasks, audit, specification, backend, boundary_policy, stream)
    except BaseException as exc:
        write_new(output_dir / "run-state.json", {"status": "incomplete", "exception_type": type(exc).__name__,
                                                  "wall_seconds": perf_counter() - started})
        raise
    write_new(output_dir / "run-state.json", {
        "status": "completed", "wall_seconds": perf_counter() - started,
        "events_sha256": hashlib.sha256((output_dir / "events.jsonl").read_bytes()).hexdigest(),
        "config_sha256": digest(config),
    })
    return evaluate(output_dir)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--backend", choices=["mock", "openai"], default="mock")
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--api-key-env")
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--session-limit", type=int)
    parser.add_argument("--task-limit", type=int)
    parser.add_argument("--boundary-policy", choices=["reset", "preserve"], default="reset")
    args = parser.parse_args()
    backend = None
    if args.backend == "openai":
        if not args.base_url or not args.model:
            parser.error("openai backend requires --base-url and --model")
        try:
            from .model import ModelClient
        except ImportError:
            parser.error("model adapter is not installed; teammate implements cachelab.model.ModelClient")
        backend = ModelClient(args.base_url, args.model, api_key_env=args.api_key_env,
                              timeout=args.timeout, max_tokens=args.max_tokens)
    report = execute(args.course_zip, args.output_dir, backend, args.session_limit,
                     args.task_limit, args.boundary_policy)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "EXPERIMENT_COMPLETED" or any(row["model_errors"] for row in report["results"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
