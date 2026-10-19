from copy import deepcopy
import io
import json
import unittest

from cachelab.replay import stream_strategy


def fixture():
    graph = {'nodes': [{'id': 1, 'class_name': 'plate'}], 'edges': []}
    gold = {'location': {'plate': {'object': 'plate', 'container': None, 'room': None}},
            'summary_slots': {'plate': 'IDLE in unknown'}}
    task = {'target_objects': ['plate'], 'steps': [{'graph': graph, 'gold': gold, 'action': 'test'}] * 2}
    return ([{'session_id': 's', 'task_ids': ['a', 'b']}], {'a': task, 'b': task},
            {'graph_discontinuities': [{'session_id': 's', 'task_id': 'b'}]})


def events(backend=None, policy='reset', sessions=None):
    selected, tasks, audit = fixture()
    out = io.StringIO()
    stream_strategy(selected if sessions is None else sessions, tasks, audit,
                    ('dependency-fine', 'dependency', 5, 'fine'), backend, policy, out)
    return [json.loads(line) for line in out.getvalue().splitlines()]


class BrokenAdapter:
    def generate(self, kind, target, graph):
        raise TimeoutError('private error detail')


class ReplayTests(unittest.TestCase):
    def test_reset_boundaries_and_reuse_sources(self):
        log = events()
        requests = [e for e in log if e['event_type'] == 'request']
        self.assertEqual(len(requests), 8)
        self.assertEqual(sum(e['reused'] for e in requests), 4)
        by_id = {e['event_id']: e for e in requests}
        self.assertEqual(len(by_id), 8)
        for event in requests:
            if event['reused']:
                source = by_id[event['cache_source_event_id']]
                self.assertFalse(source['reused'])
                self.assertEqual(source['cache_created_step'], event['cache_created_step'])
                self.assertEqual(source['answer'], event['answer'])
        self.assertEqual(sum(e['event_type'] == 'boundary_reset' for e in log), 1)

    def test_preserve_and_session_isolation(self):
        self.assertEqual(sum(e.get('reused', False) for e in events(policy='preserve')), 6)
        sessions = [{'session_id': 's1', 'task_ids': ['a']}, {'session_id': 's2', 'task_ids': ['a']}]
        self.assertEqual(sum(e.get('reused', False) for e in events(sessions=sessions)), 4)

    def test_exceptions_are_logged_and_retried_without_gold_fallback(self):
        requests = [e for e in events(BrokenAdapter()) if e['event_type'] == 'request']
        self.assertTrue(all(e['answer'] is None and not e['reused'] for e in requests))
        self.assertTrue(all(e['error'] == 'backend_exception:TimeoutError' for e in requests))
        self.assertNotIn('private error detail', str(requests))

    def test_backend_input_does_not_include_gold_or_strategy(self):
        seen = []
        class Recorder:
            def generate(self, kind, target, graph):
                seen.append(deepcopy(graph))
                return {'answer': {}, 'raw_output': '{}', 'error': None, 'latency_seconds': 0}
        events(Recorder())
        self.assertTrue(seen)
        self.assertTrue(all(set(g) == {'nodes', 'edges'} for g in seen))
        self.assertTrue(all(g == seen[0] for g in seen))


if __name__ == '__main__':
    unittest.main()
