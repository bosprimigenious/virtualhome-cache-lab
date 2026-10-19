"""Bind event evidence to a frozen input manifest and cache provenance."""
import hashlib
import json

from .core import canonical, projection
from .judge import VERSION
from .replay import STRATEGIES, digest


IDENTITY_FIELDS = ('session_id', 'task_id', 'task_step', 'kind', 'target')


def build_manifest(sessions, tasks):
    manifest = []
    for session in sessions:
        for task_id in session['task_ids']:
            task = tasks[task_id]
            for task_step, state in enumerate(task['steps'], 1):
                for kind, target in [("location", x) for x in task['target_objects']] + [('summary', None)]:
                    gold = (state['gold']['location'][target] if kind == 'location' else state['gold']['summary_slots'])
                    manifest.append({
                        'session_id': session['session_id'], 'task_id': task_id, 'task_step': task_step,
                        'kind': kind, 'target': target, 'gold_sha256': digest(gold),
                        'model_input_sha256': digest(state['graph']),
                        'dependency_sha256': {g: digest(projection(state['graph'], kind, target, g, True))
                                              for g in ('fine', 'coarse')},
                    })
    return manifest


def validate(events, config, state, raw):
    errors = []
    if config['judge_version'] != VERSION:
        errors.append('judge_version_mismatch')
    if state.get('events_sha256') != hashlib.sha256(raw).hexdigest():
        errors.append('event_log_digest_mismatch')
    if state.get('config_sha256') != digest(config):
        errors.append('config_digest_mismatch')
    manifest = {tuple(row[f] for f in IDENTITY_FIELDS): row for row in config['request_manifest']}
    specifications = {row[0]: row for row in STRATEGIES}
    expected = {(strategy, *key) for strategy in config['strategies'] for key in manifest}
    actual = set()
    active_sources = {}
    for event in events:
        typ = event.get('event_type')
        strategy_id, session_id = event.get('strategy_id'), event.get('session_id')
        if typ in {'session_start', 'boundary_reset'}:
            active_sources = {key: value for key, value in active_sources.items()
                              if key[:2] != (strategy_id, session_id)}
            continue
        if typ != 'request':
            errors.append('unknown_event_type')
            continue
        identity = (strategy_id, *(event[f] for f in IDENTITY_FIELDS))
        if identity in actual:
            errors.append('duplicate_request_identity')
        actual.add(identity)
        row = manifest.get(identity[1:])
        if row is None or strategy_id not in specifications or identity not in expected:
            errors.append('unexpected_request_identity')
            continue
        spec = specifications[strategy_id]
        if (event['backend'] != config['backend'] or event['strategy'] != spec[1]
                or event['granularity'] != spec[3]):
            errors.append('event_configuration_mismatch')
        if event['event_id'] != digest(list(identity)):
            errors.append('event_id_mismatch')
        if (digest(event['gold']) != row['gold_sha256']
                or event['model_input_sha256'] != row['model_input_sha256']):
            errors.append('source_manifest_mismatch')
        if (digest(event['dependencies']) != event['dependency_sha256']
                or event['dependency_sha256'] != row['dependency_sha256'][spec[3]]):
            errors.append('dependency_manifest_mismatch')
        if event['model_input'] is not None and digest(event['model_input']) != row['model_input_sha256']:
            errors.append('model_input_mismatch')
        key = (strategy_id, session_id, event['kind'], event['target'])
        prior = active_sources.get(key)
        if event['had_prior'] != (prior is not None):
            errors.append('prior_cache_presence_mismatch')
        if prior is not None and (event['prior_gold'] != prior['gold'] or event['prior_answer'] != prior['answer']):
            errors.append('prior_cache_evidence_mismatch')
        if event['reused']:
            if (prior is None or event['cache_source_event_id'] != prior['event_id']
                    or event['answer'] != prior['answer']
                    or event['cache_created_step'] != prior['cache_created_step']):
                errors.append('cache_source_mismatch')
            if event['error'] is not None or event['latency_seconds'] != 0:
                errors.append('reused_event_contains_call')
        elif event['error'] is None and isinstance(event['answer'], dict):
            active_sources[key] = event
        elif event['answer'] is not None:
            errors.append('failed_call_has_answer')
    if actual != expected:
        errors.append('request_manifest_mismatch')
    return sorted(set(errors))
