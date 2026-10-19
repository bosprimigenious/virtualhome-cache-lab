from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cachelab.evaluate import aggregate, evaluate
from cachelab.experiment import execute
from cachelab.judge import correct
from cachelab.core import projection


def fixture():
    graph = {"nodes": [{"id": 1, "class_name": "plate", "states": []}], "edges": []}
    gold = {"location": {"plate": {"object": "plate", "container": None, "room": "secret-gold-room"}},
            "summary_slots": {"plate": "IDLE in secret-gold-room"}}
    state = {"graph": graph, "gold": gold, "action": "test"}
    tasks = {name: {"target_objects": ["plate"], "steps": [deepcopy(state), deepcopy(state)]}
             for name in ("a", "b")}
    sessions = [{"session_id": "s", "task_ids": ["a", "b"]}]
    audit = {"graph_discontinuities": [{"session_id": "s", "task_id": "b"}]}
    return sessions, tasks, audit


class FakeModel:
    def __init__(self, fail=False):
        self.graphs = []
        self.fail = fail

    def configuration(self):
        return {"model": "test-double"}

    def generate(self, kind, target, graph):
        self.graphs.append(deepcopy(graph))
        return {"answer": None if self.fail else {"incorrect": "prediction"},
                "raw_output": "invalid" if self.fail else '{"incorrect":"prediction"}',
                "error": "http_error:503" if self.fail else None,
                "error_type": "transport" if self.fail else None,
                "latency_seconds": 0.1, "usage": {}, "finish_reason": "stop"}


class ExperimentTests(unittest.TestCase):
    def test_mock_complete_and_rebuild_without_changing_events(self):
        with tempfile.TemporaryDirectory() as tmp, patch('cachelab.experiment.load_course', return_value=fixture()):
            directory = Path(tmp) / 'run'
            report = execute('unused.zip', directory)
            self.assertEqual(report['status'], 'EXPERIMENT_COMPLETED')
            self.assertEqual(len(report['results']), 6)
            for row in report['results']:
                self.assertEqual(row['requests'], 8)
                self.assertEqual(row['model_errors'], 0)
                self.assertIsNone(row['real_llm_latency_seconds'])
                if row['strategy_id'].startswith('dependency'):
                    self.assertEqual(row['decision_calls'], 4)
            before = (directory / 'events.jsonl').read_bytes()
            self.assertEqual(evaluate(directory), report)
            self.assertEqual((directory / 'events.jsonl').read_bytes(), before)
            with self.assertRaises(FileExistsError):
                execute('unused.zip', directory)

    def test_preserve_is_explicit_and_separate(self):
        with tempfile.TemporaryDirectory() as tmp, patch('cachelab.experiment.load_course', return_value=fixture()):
            report = execute('unused.zip', Path(tmp) / 'run', boundary_policy='preserve')
            fine = next(r for r in report['results'] if r['strategy_id'] == 'dependency-fine')
            self.assertEqual(fine['decision_calls'], 2)

    def test_transport_failure_not_cached_or_replaced_by_gold(self):
        with tempfile.TemporaryDirectory() as tmp, patch('cachelab.experiment.load_course', return_value=fixture()):
            directory = Path(tmp) / 'run'
            model = FakeModel(fail=True)
            report = execute('unused.zip', directory, backend=model)
            for row in report['results']:
                self.assertEqual(row['decision_calls'], 8)
                self.assertEqual(row['transport_errors'], 8)
                self.assertEqual(row['correct_answers'], 0)
            self.assertEqual(len(model.graphs), 48)
            self.assertNotIn('secret-gold-room', json.dumps(model.graphs))

    def test_model_error_reuse_not_misattributed_to_state_change(self):
        with tempfile.TemporaryDirectory() as tmp, patch('cachelab.experiment.load_course', return_value=fixture()):
            model = FakeModel()
            report = execute('unused.zip', Path(tmp) / 'run', backend=model)
            fine = next(r for r in report['results'] if r['strategy_id'] == 'dependency-fine')
            self.assertEqual(fine['model_error_reuse'], 4)
            self.assertEqual(fine['missed_invalidation'], 0)
            self.assertEqual(fine['stale_reuse'], 4)
            self.assertEqual(fine['invalidation_accuracy'], 1.0)
            self.assertTrue(all(g == model.graphs[0] for g in model.graphs))

    def test_missing_event_counts_cannot_pass_completion(self):
        with tempfile.TemporaryDirectory() as tmp, patch('cachelab.experiment.load_course', return_value=fixture()):
            directory = Path(tmp) / 'run'
            execute('unused.zip', directory)
            events = (directory / 'events.jsonl').read_text().splitlines()
            (directory / 'events.jsonl').write_text('\n'.join(events[:-1]) + '\n')
            self.assertEqual(evaluate(directory)['status'], 'INCOMPLETE')

    def test_course_dependencies_preserve_gold_sensitive_edge_order(self):
        graph = {"nodes": [
            {"id": 1, "class_name": "plate"},
            {"id": 2, "class_name": "kitchen", "category": "Rooms"},
            {"id": 3, "class_name": "bedroom", "category": "Rooms"}],
            "edges": [{"from_id": 1, "relation_type": "IN", "to_id": 2},
                      {"from_id": 1, "relation_type": "IN", "to_id": 3}]}
        changed = deepcopy(graph)
        changed['edges'].reverse()
        for granularity in ('fine', 'coarse'):
            self.assertNotEqual(projection(graph, 'location', 'plate', granularity, True),
                                projection(changed, 'location', 'plate', granularity, True))

    def test_course_dependencies_follow_reverse_in_without_expanding_rooms(self):
        graph = {"nodes": [
            {"id": 1, "class_name": "plate"}, {"id": 2, "class_name": "box"},
            {"id": 3, "class_name": "kitchen", "category": "Rooms"},
            {"id": 4, "class_name": "tv"}],
            "edges": [{"from_id": 2, "relation_type": "IN", "to_id": 1},
                      {"from_id": 2, "relation_type": "IN", "to_id": 3},
                      {"from_id": 4, "relation_type": "IN", "to_id": 3}]}
        deps = projection(graph, 'location', 'plate', course_semantics=True)
        self.assertEqual({n['id'] for n in deps['nodes']}, {1, 2, 3})
        changed = deepcopy(graph)
        changed['edges'][1]['to_id'] = 4
        self.assertNotEqual(deps, projection(changed, 'location', 'plate', course_semantics=True))

    def test_judge_state_order_but_not_room(self):
        self.assertTrue(correct({'tv': 'OFF CLOSED in kitchen'}, {'tv': 'closed off in kitchen'}, 'summary'))
        self.assertFalse(correct({'tv': 'OFF in kitchen'}, {'tv': 'OFF in bedroom'}, 'summary'))

    def test_duplicate_event_with_same_total_is_not_complete(self):
        with tempfile.TemporaryDirectory() as tmp, patch('cachelab.experiment.load_course', return_value=fixture()):
            directory = Path(tmp) / 'run'
            execute('unused.zip', directory)
            events = (directory / 'events.jsonl').read_text().splitlines()
            indices = [i for i, line in enumerate(events) if json.loads(line)['event_type'] == 'request']
            events[indices[1]] = events[indices[0]]
            (directory / 'events.jsonl').write_text('\n'.join(events) + '\n')
            report = evaluate(directory)
            self.assertEqual(report['status'], 'INCOMPLETE')
            self.assertIn('duplicate_request_identity', report['integrity_errors'])

    def test_partial_stream_is_not_complete(self):
        with tempfile.TemporaryDirectory() as tmp, patch('cachelab.experiment.load_course', return_value=fixture()):
            directory = Path(tmp) / 'run'
            execute('unused.zip', directory)
            (directory / 'run-state.json').write_text('{"status":"incomplete"}')
            self.assertEqual(evaluate(directory)['status'], 'INCOMPLETE')


if __name__ == '__main__':
    unittest.main()
