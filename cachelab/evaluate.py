"""Rebuild metric artifacts solely from append-only event logs."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from .judge import correct
from .evidence import validate


def aggregate(events, split_kind=False):
    groups = {}
    for event in events:
        if event.get("event_type") != "request":
            continue
        group_id = event["strategy_id"] + ("/" + event["kind"] if split_kind else "")
        if group_id not in groups:
            groups[group_id] = {"counts": Counter(), "latency": 0.0, "request_wall": 0.0}
        group = groups[group_id]
        c = group["counts"]
        c["requests"] += 1
        reused = event["reused"]
        c["reuse_events" if reused else "decision_calls"] += 1
        valid = correct(event["answer"], event["gold"], event["kind"])
        c["correct_answers"] += int(valid)
        c["invalid_json_or_schema"] += int(event.get("error_type") == "output")
        c["transport_errors"] += int(event.get("error_type") == "transport")
        c["model_errors"] += int(bool(event.get("error")))
        if reused:
            c["valid_reuse" if valid else "stale_reuse"] += 1
        else:
            c["fresh_correct"] += int(valid)
            c["fresh_incorrect"] += int(not valid)
        if event["had_prior"]:
            gold_changed = not correct(event["prior_gold"], event["gold"], event["kind"])
            prior_wrong_at_birth = not correct(event["prior_answer"], event["prior_gold"], event["kind"])
            c["prior_opportunities"] += 1
            if reused:
                c["correct_retention"] += int(not gold_changed)
                c["missed_invalidation"] += int(gold_changed)
                c["state_stale_reuse"] += int(gold_changed and not valid)
                c["model_error_reuse"] += int(not gold_changed and not valid and prior_wrong_at_birth)
            elif event["strategy"] != "none":
                c["invalidation_events"] += 1
                c["false_invalidation"] += int(not gold_changed)
                c["correct_invalidation"] += int(gold_changed)
        group["latency"] += event["latency_seconds"]
        group["request_wall"] += event["request_wall_seconds"]
        group["backend"] = event["backend"]
        group["strategy"] = event["strategy"]
    rows = []
    fields = ["requests", "decision_calls", "reuse_events", "correct_answers", "valid_reuse",
              "stale_reuse", "fresh_correct", "fresh_incorrect", "model_errors", "invalid_json_or_schema", "transport_errors",
              "prior_opportunities", "missed_invalidation", "state_stale_reuse", "model_error_reuse",
              "invalidation_events", "false_invalidation", "correct_invalidation", "correct_retention"]
    for strategy_id, group in groups.items():
        c = group["counts"]
        assert c["requests"] == c["decision_calls"] + c["reuse_events"]
        assert c["reuse_events"] == c["valid_reuse"] + c["stale_reuse"]
        rows.append({"strategy_id": strategy_id, "backend": group["backend"],
                     **{field: c[field] for field in fields},
                     "valid_reuse_rate": c["valid_reuse"] / c["reuse_events"] if c["reuse_events"] else None,
                     "stale_reuse_rate": c["stale_reuse"] / c["reuse_events"] if c["reuse_events"] else None,
                     "answer_accuracy": c["correct_answers"] / c["requests"],
                     "evaluation_model_calls": 0,
                     "invalidation_accuracy": ((c["correct_invalidation"] + c["correct_retention"]) /
                                               c["prior_opportunities"]
                                               if c["prior_opportunities"] and group["strategy"] != "none" else None),
                     "request_wall_seconds": group["request_wall"],
                     "real_llm_latency_seconds": group["latency"] if group["backend"] == "openai" else None,
                     "mock_compute_seconds": group["latency"] if group["backend"] == "mock" else None})
    return rows


def evaluate(directory):
    directory = Path(directory)
    events = []
    raw = (directory / "events.jsonl").read_bytes()
    with (directory / "events.jsonl").open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid event JSON at line {line_number}") from exc
    rows = aggregate(events)
    config = json.loads((directory / "config.json").read_text())
    expected = set(config["strategies"])
    state_path = directory / "run-state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"status": "incomplete"}
    integrity_errors = validate(events, config, state, raw)
    complete = (not integrity_errors and state["status"] == "completed" and {r["strategy_id"] for r in rows} == expected
                and all(r["requests"] == config["expected_requests_per_strategy"] for r in rows))
    status = "EXPERIMENT_COMPLETED" if complete else "INCOMPLETE"
    if complete and any(row["model_errors"] for row in rows):
        status = "COMPLETED_WITH_MODEL_ERRORS"
    report = {"status": status,
              "course_acceptance": "NOT_READY", "integrity_errors": sorted(set(integrity_errors)),
              "backend": config["backend"],
              "judge_version": config["judge_version"], "results": rows,
              "by_kind": aggregate(events, split_kind=True), "run_state": state}
    # Derived artifacts can be rebuilt; config and raw events are never rewritten.
    (directory / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if rows:
        with (directory / "comparison.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    fields = ["strategy_id", "requests", "decision_calls", "reuse_events", "stale_reuse_rate",
              "answer_accuracy", "model_errors", "missed_invalidation", "false_invalidation"]
    lines = ["# " + report["status"], "", "课程完整验收：NOT_READY。Mock 不是真实模型结果。", "",
             "| " + " | ".join(fields) + " |", "| " + " | ".join(["---"] * len(fields)) + " |"]
    lines += ["| " + " | ".join(str(row[field]) for field in fields) + " |" for row in rows]
    (directory / "comparison.md").write_text("\n".join(lines) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    report = evaluate(args.directory)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "EXPERIMENT_COMPLETED" or any(row["model_errors"] for row in report["results"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
