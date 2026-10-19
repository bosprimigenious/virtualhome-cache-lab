"""Aggregate acceptance for bosprimigenious's offline integration scope."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from .demo import write_demo
from .evaluate import evaluate
from .experiment import execute


class FaultBackend:
    def configuration(self):
        return {'model': 'simulated_backend_failure', 'provenance': 'test_double'}

    def generate(self, kind, target, graph):
        raise TimeoutError('controlled test-double failure')


def gate(output_dir, course_zip=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    checks = []
    if course_zip is None:
        course_zip = output_dir / 'self-authored-demo.zip'
        write_demo(course_zip)
    def check(name, operation):
        try:
            detail = operation()
            checks.append({'check': name, 'status': 'PASS', 'detail': detail})
        except Exception as exc:
            checks.append({'check': name, 'status': 'FAIL', 'error_type': type(exc).__name__, 'detail': str(exc)})

    def unit_tests():
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                                cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True)
        (output_dir / 'unit-tests.log').write_text(result.stdout + result.stderr)
        if result.returncode:
            raise ValueError('unit tests failed; inspect unit-tests.log')
        return 'unit tests passed; full output in unit-tests.log'
    check('unit_tests', unit_tests)

    def replay(policy):
        path = output_dir / policy
        report = execute(course_zip, path, boundary_policy=policy)
        if report['status'] != 'EXPERIMENT_COMPLETED':
            raise ValueError('replay did not complete with verified evidence')
        raw = (path / 'events.jsonl').read_bytes()
        rebuilt = evaluate(path)
        if rebuilt != report or (path / 'events.jsonl').read_bytes() != raw:
            raise ValueError('rebuild changed metrics or raw events')
        for row in report['results']:
            if row['strategy_id'].startswith('dependency') and row['stale_reuse']:
                raise ValueError('dependency strategy reused an incorrect oracle answer')
            if row['real_llm_latency_seconds'] is not None or row['model_errors']:
                raise ValueError('mock mislabeled as real model or unexpected errors')
        return {r['strategy_id']: {'requests': r['requests'], 'calls': r['decision_calls'],
                                   'stale_reuse': r['stale_reuse']} for r in report['results']}
    check('reset_replay_and_immutable_rebuild', lambda: replay('reset'))
    check('preserve_replay_and_immutable_rebuild', lambda: replay('preserve'))

    def failure():
        path = output_dir / 'backend-failure'
        report = execute(course_zip, path, backend=FaultBackend(), session_limit=1, task_limit=1)
        if report['status'] != 'COMPLETED_WITH_MODEL_ERRORS':
            raise ValueError('backend failure incorrectly passed')
        for row in report['results']:
            if row['reuse_events'] or row['correct_answers'] or row['model_errors'] != row['requests']:
                raise ValueError('failed generation was cached or replaced with gold')
        result = subprocess.run([sys.executable, '-m', 'cachelab.evaluate', str(path.resolve())],
                                capture_output=True, text=True)
        if result.returncode != 2:
            raise ValueError('failed experiment evaluation did not exit 2')
        return 'all failures retained; no reuse or gold fallback; evaluation CLI exits 2'
    check('backend_failure_and_cli_exit', failure)

    def tamper():
        path = output_dir / 'tampered-copy'
        shutil.copytree(output_dir / 'reset', path)
        events = [json.loads(line) for line in (path / 'events.jsonl').read_text().splitlines()]
        request = next(e for e in events if e['event_type'] == 'request')
        request['task_id'] = 'nonexistent-task'
        (path / 'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
        report = evaluate(path)
        if report['status'] != 'INCOMPLETE' or 'request_manifest_mismatch' not in report['integrity_errors']:
            raise ValueError('identity substitution bypassed evidence verification')
        return 'modified log rejected against digest and expected input identities'
    check('tampered_log_rejected', tamper)
    report = {'scope': 'bosprimigenious_offline_integration',
              'status': 'READY' if all(c['status'] == 'PASS' for c in checks) else 'NOT_READY',
              'course_acceptance': 'NOT_READY', 'real_model_verified': False,
              'checks': checks}
    (output_dir / 'acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--course-zip', type=Path)
    args = parser.parse_args()
    report = gate(args.output_dir, args.course_zip)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report['status'] != 'READY':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
