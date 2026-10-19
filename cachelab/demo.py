"""Self-authored toy fixture. Not VirtualHome simulator or course data."""
from copy import deepcopy
import json
from zipfile import ZipFile


def write_demo(path):
    def frame(room='kitchen', tv='OFF'):
        room_id = 3 if room == 'kitchen' else 4
        graph = {'nodes': [
            {'id': 1, 'class_name': 'plate', 'states': ['CLEAN']},
            {'id': 2, 'class_name': 'cabinet', 'states': ['CLOSED']},
            {'id': 3, 'class_name': 'kitchen', 'category': 'Rooms'},
            {'id': 4, 'class_name': 'bedroom', 'category': 'Rooms'},
            {'id': 5, 'class_name': 'tv', 'states': [tv]}],
            'edges': [{'from_id': 1, 'relation_type': 'IN', 'to_id': 2},
                      {'from_id': 2, 'relation_type': 'IN', 'to_id': room_id},
                      {'from_id': 5, 'relation_type': 'IN', 'to_id': 3}]}
        return {'action': 'self_authored_fixture', 'graph': graph,
                'gold': {'location': {'plate': {'object': 'plate', 'container': 'cabinet', 'room': room}},
                         'summary_slots': {'plate': 'CLEAN in '+room, 'tv': tv+' in kitchen'}}}
    base, changed, moved = frame(), frame(tv='ON'), frame('bedroom', 'ON')
    specifications = [('a', base, [base, changed]), ('b', changed, [changed, moved]),
                      ('c', base, [base, base]), ('d', base, [base, base])]
    sessions = [{'session_id': 'demo_one', 'task_ids': ['a', 'b', 'c']},
                {'session_id': 'demo_two', 'task_ids': ['d']}]
    with ZipFile(path, 'x') as archive:
        archive.writestr('demo/data/sessions.json', json.dumps(sessions))
        for task_id, initial, steps in specifications:
            task = {'task_id': task_id, 'target_objects': ['plate'],
                    'initial_graph': deepcopy(initial['graph']), 'steps': deepcopy(steps)}
            archive.writestr('demo/data/tasks/'+task_id+'.json', json.dumps(task))
