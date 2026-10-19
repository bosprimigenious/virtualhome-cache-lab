import unittest
from cachelab.backend import invoke


class Adapter:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error
    def generate(self, kind, target, graph):
        graph.clear()
        if self.error:
            raise self.error
        return self.result


def response(**changes):
    return {'answer': {}, 'raw_output': '{}', 'error': None,
            'error_type': None, 'latency_seconds': 0.1, **changes}


class BackendTests(unittest.TestCase):
    def test_graph_isolation_and_event_fields_are_not_overridable(self):
        graph = {'nodes': [], 'edges': []}
        result = invoke(Adapter(response(gold={'leak': 1}, reused=True)), 'summary', None, graph)
        self.assertEqual(graph, {'nodes': [], 'edges': []})
        self.assertNotIn('gold', result)
        self.assertNotIn('reused', result)

    def test_exceptions_become_failure_without_secret_exception_text(self):
        result = invoke(Adapter(error=RuntimeError('private-key')), 'summary', None, {})
        self.assertEqual(result['error'], 'backend_exception:RuntimeError')
        self.assertNotIn('private-key', str(result))
        self.assertIsNone(result['answer'])

    def test_bad_latency_or_missing_answer_is_a_failed_result(self):
        for result in [None, response(latency_seconds=float('nan')), response(latency_seconds=-1),
                       response(answer=None), response(error_type='typo'), response(error=''),
                       response(error_type='transport')]:
            with self.subTest(result=result):
                self.assertEqual(invoke(Adapter(result), 'summary', None, {})['error_type'], 'backend')

    def test_failed_output_can_never_be_cached_as_a_success(self):
        result = invoke(Adapter(response(error='http_error:503', error_type='transport')),
                        'summary', None, {})
        self.assertIsNone(result['answer'])
        self.assertEqual(result['error_type'], 'transport')


if __name__ == '__main__':
    unittest.main()
