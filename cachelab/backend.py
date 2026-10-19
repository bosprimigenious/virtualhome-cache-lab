"""Minimal integration boundary owned jointly with the model implementation."""
from copy import deepcopy
import math
from time import perf_counter
from typing import Protocol


class Backend(Protocol):
    def configuration(self) -> dict:
        """Return reproducible settings, without credentials."""
        ...

    def generate(self, kind: str, target: str | None, graph: dict) -> dict:
        """Return answer, raw_output, latency_seconds, error and error_type."""
        ...


def invoke(backend: Backend, kind, target, graph):
    """Turn adapter failures into audit events without exposing exception text."""
    started = perf_counter()
    try:
        result = backend.generate(kind, target, deepcopy(graph))
        if not isinstance(result, dict):
            raise ValueError('invalid result')
        latency = result['latency_seconds']
        if (not isinstance(latency, (float, int)) or isinstance(latency, bool)
                or not math.isfinite(latency) or latency < 0):
            raise ValueError('invalid latency')
        if result.get('error') is not None and not isinstance(result['error'], str):
            raise ValueError('invalid error')
        if result.get('error') is None and not isinstance(result.get('answer'), dict):
            raise ValueError('successful result must have structured answer')
        if result.get('error_type') not in {None, 'output', 'transport', 'configuration', 'backend'}:
            raise ValueError('invalid error category')
        # Allow only documented outcome fields; a backend cannot replace event identity or gold.
        allowed = ('answer', 'raw_output', 'latency_seconds', 'error', 'error_type',
                   'usage', 'finish_reason', 'response_model', 'system_fingerprint')
        outcome = {name: deepcopy(result.get(name)) for name in allowed}
        outcome['usage'] = outcome['usage'] or {}
        if outcome['error']:
            outcome['answer'] = None
            outcome['error_type'] = outcome['error_type'] or 'backend'
        return outcome
    except Exception as exc:
        return {'answer': None, 'raw_output': None,
                'latency_seconds': perf_counter() - started,
                'error': 'backend_exception:' + type(exc).__name__, 'error_type': 'backend',
                'usage': {}, 'finish_reason': None}
