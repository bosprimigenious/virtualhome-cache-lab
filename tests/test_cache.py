from copy import deepcopy
import unittest

from cachelab.core import Cache, equivalent, projection
from cachelab.run import run


def scene():
    return {"nodes": [
        {"id": 1, "class_name": "plate", "states": []},
        {"id": 2, "class_name": "cabinet", "states": ["CLOSED"]},
        {"id": 3, "class_name": "kitchen", "category": "Rooms"},
        {"id": 4, "class_name": "character"},
        {"id": 5, "class_name": "tv", "states": ["OFF"]},
    ], "edges": [
        {"from_id": 1, "relation_type": "IN", "to_id": 2},
        {"from_id": 2, "relation_type": "IN", "to_id": 3},
        {"from_id": 4, "relation_type": "IN", "to_id": 3},
    ]}


class CacheTests(unittest.TestCase):
    def test_fixed_boundary_and_no_sliding_expiry(self):
        cache = Cache("fixed", 3)
        compute = lambda: ({"x": 1}, 0.1)
        self.assertFalse(cache.request("a", 0, {}, compute)[1])
        self.assertTrue(cache.request("a", 2, {}, compute)[1])
        self.assertFalse(cache.request("a", 3, {}, compute)[1])

    def test_added_hold_edge_invalidates(self):
        before = scene()
        after = deepcopy(before)
        after["edges"].append({"from_id": 4, "relation_type": "HOLDS_RH", "to_id": 1})
        cache = Cache("dependency")
        calls = []
        def compute():
            calls.append(1)
            return {"call": len(calls)}, 0.0
        cache.request("plate", 0, projection(before, "location", "plate"), compute)
        value, reused, _ = cache.request("plate", 1, projection(after, "location", "plate"), compute)
        self.assertFalse(reused)
        self.assertEqual(value, {"call": 2})
        after["edges"].pop()
        self.assertFalse(cache.request("plate", 2, projection(after, "location", "plate"), compute)[1])

    def test_irrelevant_change_reuses_location_not_summary(self):
        before = scene()
        after = deepcopy(before)
        after["nodes"][-1]["states"] = ["ON"]
        self.assertEqual(projection(before, "location", "plate"), projection(after, "location", "plate"))
        self.assertNotEqual(projection(before, "summary"), projection(after, "summary"))
        self.assertNotEqual(projection(before, "location", "plate", "coarse"), projection(after, "location", "plate", "coarse"))

    def test_missing_object_appearance_and_container_move(self):
        before = scene()
        after = deepcopy(before)
        after["nodes"].append({"id": 8, "class_name": "mug"})
        self.assertNotEqual(projection(before, "location", "mug"), projection(after, "location", "mug"))
        after = deepcopy(before)
        after["edges"][1]["to_id"] = 4
        self.assertNotEqual(projection(before, "location", "plate"), projection(after, "location", "plate"))

    def test_order_invariance(self):
        before = scene()
        after = deepcopy(before)
        after["nodes"].reverse()
        after["edges"].reverse()
        self.assertEqual(projection(before, "summary"), projection(after, "summary"))

    def test_none_always_computes(self):
        cache = Cache("none")
        for step in range(3):
            self.assertFalse(cache.request("x", step, {}, lambda: ({}, 0))[1])

    def test_session_isolation_and_counts(self):
        gold = {"location": {"plate": {"room": "kitchen"}}, "summary_slots": {"plate": "kitchen"}}
        task = {"target_objects": ["plate"], "steps": [{"graph": scene(), "gold": gold}] * 2}
        result = run([{"task_ids": ["a"]}, {"task_ids": ["b"]}], {"a": task, "b": task}, "dependency")
        self.assertEqual(result["decision_calls"], 4)
        self.assertEqual(result["reuse_events"], 4)
        self.assertEqual(result["valid_reuse_rate"], 1.0)
        self.assertEqual(result["decision_calls"] + result["reuse_events"], result["requests"])

    def test_judge_does_not_accept_missing_or_wrong_fields(self):
        self.assertTrue(equivalent({"room": " Kitchen "}, {"room": "kitchen"}))
        self.assertFalse(equivalent({}, {"room": None}))
        self.assertFalse(equivalent({"room": "bedroom"}, {"room": "kitchen"}))


if __name__ == "__main__":
    unittest.main()
