from copy import deepcopy
import unittest

from cachelab.core import projection


def graph():
    return {"nodes": [{"id": 1, "class_name": "plate"},
                      {"id": 2, "class_name": "box"},
                      {"id": 3, "class_name": "kitchen", "category": "Rooms"},
                      {"id": 4, "class_name": "character"},
                      {"id": 5, "class_name": "bedroom", "category": "Rooms"}],
            "edges": [{"from_id": 1, "relation_type": "IN", "to_id": 2},
                      {"from_id": 2, "relation_type": "IN", "to_id": 3},
                      {"from_id": 4, "relation_type": "IN", "to_id": 3}]}


def deps(state, kind="location", target="plate", granularity="fine"):
    return projection(state, kind, target, granularity, course_semantics=True)


class DependencyTests(unittest.TestCase):
    def test_course_edge_order_is_preserved(self):
        before = graph()
        before['edges'].append({'from_id': 1, 'relation_type': 'IN', 'to_id': 5})
        after = deepcopy(before)
        after['edges'].reverse()
        for granularity in ('fine', 'coarse'):
            self.assertNotEqual(deps(before, granularity=granularity), deps(after, granularity=granularity))

    def test_reverse_in_paths_stop_at_rooms(self):
        state = graph()
        state['edges'][0] = {'from_id': 2, 'relation_type': 'IN', 'to_id': 1}
        self.assertEqual({n['id'] for n in deps(state)['nodes']}, {1, 2, 3})
        changed = deepcopy(state)
        changed['edges'][1]['to_id'] = 5
        self.assertNotEqual(deps(state), deps(changed))

    def test_hold_add_remove_and_holder_move(self):
        before = graph()
        held = deepcopy(before)
        held['edges'].append({'from_id': 4, 'relation_type': 'HOLDS_LH', 'to_id': 1})
        moved = deepcopy(held)
        moved['edges'][2]['to_id'] = 5
        self.assertNotEqual(deps(before), deps(held))
        self.assertNotEqual(deps(held), deps(moved))
        self.assertNotEqual(deps(moved), deps(before))

    def test_target_deletion_and_appearance(self):
        before = graph()
        removed = deepcopy(before)
        removed['nodes'] = [n for n in removed['nodes'] if n['id'] != 1]
        removed['edges'] = removed['edges'][1:]
        self.assertNotEqual(deps(before), deps(removed))
        self.assertEqual(deps(removed), {'nodes': [], 'edges': []})

    def test_container_move_and_summary_state_flip(self):
        before = graph()
        moved = deepcopy(before)
        moved['edges'][1]['to_id'] = 5
        self.assertNotEqual(deps(before), deps(moved))
        changed = deepcopy(before)
        changed['nodes'][1]['states'] = ['CLOSED']
        self.assertNotEqual(deps(before, 'summary'), deps(changed, 'summary'))

    def test_unrelated_state_does_not_invalidate_fine(self):
        before = graph()
        changed = deepcopy(before)
        changed['nodes'][3]['states'] = ['SITTING']
        self.assertEqual(deps(before), deps(changed))
        self.assertNotEqual(deps(before, granularity='coarse'), deps(changed, granularity='coarse'))

    def test_same_class_instances_and_cycles(self):
        state = graph()
        state['nodes'].append({'id': 6, 'class_name': 'plate'})
        state['edges'].extend([{'from_id': 6, 'relation_type': 'IN', 'to_id': 1},
                               {'from_id': 1, 'relation_type': 'IN', 'to_id': 6}])
        self.assertTrue({1, 6}.issubset({n['id'] for n in deps(state)['nodes']}))

    def test_unknown_query_or_granularity_rejected(self):
        with self.assertRaises(ValueError):
            deps(graph(), kind='typo')
        with self.assertRaises(ValueError):
            deps(graph(), granularity='typo')


if __name__ == '__main__':
    unittest.main()
