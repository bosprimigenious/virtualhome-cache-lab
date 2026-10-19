import unittest

from cachelab.core import Cache, canonical


class DecisionTests(unittest.TestCase):
    def test_miss_dependency_hit_and_change_reasons(self):
        cache = Cache('dependency')
        self.assertEqual(cache.decision('x', 1, {})[:2], (False, 'miss'))
        cache.store('x', 1, canonical({}), {'answer': 1})
        self.assertEqual(cache.decision('x', 2, {})[:2], (True, 'dependencies_unchanged'))
        self.assertEqual(cache.decision('x', 3, {'new': 1})[:2], (False, 'dependencies_changed'))

    def test_fixed_window_never_slides_on_reuse(self):
        cache = Cache('fixed', k=3)
        cache.request('x', 1, {}, lambda: ({'answer': 1}, 0))
        self.assertEqual(cache.decision('x', 3, {})[:2], (True, 'ttl_valid'))
        cache.request('x', 3, {}, lambda: self.fail('must not compute'))
        self.assertEqual(cache.decision('x', 4, {})[:2], (False, 'ttl_expired'))

    def test_none_and_clear(self):
        cache = Cache('none')
        cache.request('x', 1, {}, lambda: ({}, 0))
        self.assertEqual(cache.decision('x', 2, {})[:2], (False, 'always_recompute'))
        cache.clear()
        self.assertEqual(cache.decision('x', 3, {})[:2], (False, 'miss'))

    def test_mutation_cannot_change_stored_answer(self):
        cache = Cache('dependency')
        value = {'nested': [1]}
        cache.store('x', 0, canonical({}), value)
        value['nested'].append(2)
        returned, _, _ = cache.request('x', 1, {}, lambda: self.fail('cache hit'))
        self.assertEqual(returned, {'nested': [1]})
        returned['nested'].append(3)
        self.assertEqual(cache.entries['x'][2], {'nested': [1]})

    def test_failed_compute_does_not_replace_entry(self):
        cache = Cache('dependency')
        cache.store('x', 0, canonical({}), {'answer': 'old'})
        def fail():
            raise TimeoutError('test')
        with self.assertRaises(TimeoutError):
            cache.request('x', 1, {'changed': 1}, fail)
        self.assertEqual(cache.entries['x'][2], {'answer': 'old'})
        with self.assertRaises(ValueError):
            cache.store('new', 2, canonical({}), None)
        self.assertNotIn('new', cache.entries)


if __name__ == '__main__':
    unittest.main()
