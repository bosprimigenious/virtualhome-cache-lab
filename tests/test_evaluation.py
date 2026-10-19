import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from cachelab.evidence import build_manifest
from cachelab.evaluate import evaluate
from cachelab.judge import VERSION, correct
from cachelab.replay import STRATEGIES, digest, stream_strategy


def write_fixture(directory):
    graph = {'nodes': [{'id': 1, 'class_name': 'plate'}], 'edges': []}
    gold = {'location': {'plate': {'object': 'plate', 'container': None, 'room': None}},
            'summary_slots': {'plate': 'IDLE in unknown'}}
    tasks = {'a': {'target_objects': ['plate'], 'steps': [{'graph': graph, 'gold': gold}] * 2}}
    sessions = [{'session_id': 's', 'task_ids': ['a']}]
    config = {'backend': 'mock', 'strategies': [s[0] for s in STRATEGIES], 'judge_version': VERSION,
              'expected_requests_per_strategy': 4, 'request_manifest': build_manifest(sessions, tasks)}
    stream = io.StringIO()
    for spec in STRATEGIES:
        stream_strategy(sessions, tasks, {'graph_discontinuities': []}, spec, None, 'reset', stream)
    raw = stream.getvalue().encode()
    state = {'status': 'completed', 'events_sha256': hashlib.sha256(raw).hexdigest(),
             'config_sha256': digest(config)}
    (directory / 'events.jsonl').write_bytes(raw)
    (directory / 'config.json').write_text(json.dumps(config))
    (directory / 'run-state.json').write_text(json.dumps(state))


class EvaluationTests(unittest.TestCase):
    def test_rebuild_preserves_events_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            write_fixture(p)
            before = (p / 'events.jsonl').read_bytes()
            result = evaluate(p)
            self.assertEqual(result['status'], 'EXPERIMENT_COMPLETED')
            self.assertEqual(result, evaluate(p))
            self.assertEqual(before, (p / 'events.jsonl').read_bytes())
            self.assertEqual(len(result['by_kind']), 12)

    def test_manifest_identity_backend_gold_and_cache_source_tampering(self):
        mutations = [lambda e: e.update(task_id='missing'),
                     lambda e: e.update(backend='unknown'),
                     lambda e: e.update(gold={'forged': True}, answer={'forged': True}),
                     lambda e: e.update(cache_source_event_id='missing', answer={'forged': True}),
                     lambda e: e.update(dependency_sha256='fake'),
                     lambda e: e.update(reason='fabricated_hit'),
                     lambda e: e.update(session_step=999)]
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp)
                write_fixture(p)
                events = [json.loads(line) for line in (p / 'events.jsonl').read_text().splitlines()]
                target = next(e for e in events if e.get('reused'))
                mutate(target)
                raw = ''.join(json.dumps(e)+'\n' for e in events).encode()
                (p / 'events.jsonl').write_bytes(raw)
                # Re-sealing alone cannot bypass manifest and cache provenance checks.
                state = json.loads((p / 'run-state.json').read_text())
                state['events_sha256'] = hashlib.sha256(raw).hexdigest()
                (p / 'run-state.json').write_text(json.dumps(state))
                self.assertEqual(evaluate(p)['status'], 'INCOMPLETE')

    def test_invalid_fresh_outcome_or_latency_cannot_pass(self):
        for changes in ({'model_input': None}, {'answer': None, 'error': None},
                        {'latency_seconds': -1}, {'latency_seconds': float('nan')},
                        {'error': '', 'error_type': 'transport'}):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp)
                write_fixture(p)
                events = [json.loads(line) for line in (p / 'events.jsonl').read_text().splitlines()]
                target = next(e for e in events if e.get('event_type') == 'request' and not e['reused'])
                target.update(changes)
                raw = ''.join(json.dumps(e)+'\n' for e in events).encode()
                (p / 'events.jsonl').write_bytes(raw)
                state = json.loads((p / 'run-state.json').read_text())
                state['events_sha256'] = hashlib.sha256(raw).hexdigest()
                (p / 'run-state.json').write_text(json.dumps(state))
                report = evaluate(p)
                self.assertEqual(report['status'], 'INCOMPLETE')
                self.assertIn('invalid_request_schema', report['integrity_errors'])

    def test_missing_digest_and_unknown_judge_are_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            write_fixture(p)
            config = json.loads((p / 'config.json').read_text())
            config['judge_version'] = 'future-rule-not-installed'
            (p / 'config.json').write_text(json.dumps(config))
            result = evaluate(p)
            self.assertIn('judge_version_mismatch', result['integrity_errors'])
            self.assertIn('config_digest_mismatch', result['integrity_errors'])

    def test_state_word_order_is_normalized_but_not_room(self):
        self.assertTrue(correct({'tv': 'OFF CLOSED in kitchen'}, {'tv': 'closed off in kitchen'}, 'summary'))
        self.assertFalse(correct({'tv': 'OFF in kitchen'}, {'tv': 'OFF in bedroom'}, 'summary'))


if __name__ == '__main__':
    unittest.main()
