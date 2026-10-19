"""Cache dependencies describe query input, including absent edges and objects."""
from copy import deepcopy
import json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def projection(graph, kind, target=None, granularity="fine"):
    """Return exact model input. Recompare input to catch additions and removals.

    Fine location input follows IN/ON ancestors and reverse HOLDS edges. Summary
    consumes the entire graph. Coarse deliberately uses the entire graph for both:
    this is a conservative baseline, not the teacher package's room-only policy.
    """
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = graph["edges"]
    keep = set(nodes)
    if kind == "location" and granularity == "fine":
        keep = {n["id"] for n in nodes.values() if n["class_name"] == target}
        # All matching instances remain visible; no implicit first-instance choice.
        while True:
            extra = set(keep)
            for edge in edges:
                a, b, rel = edge["from_id"], edge["to_id"], edge["relation_type"]
                if a in keep and rel in {"IN", "ON"}:
                    extra.add(b)
                if b in keep and rel in {"HOLDS_RH", "HOLDS_LH"}:
                    extra.add(a)
            if extra == keep:
                break
            keep = extra
    clean_nodes = []
    for node_id in sorted(keep):
        if node_id in nodes:
            node = deepcopy(nodes[node_id])
            for field in ("states", "properties"):
                node[field] = sorted(node.get(field, []))
            clean_nodes.append(node)
    clean_edges = sorted(
        [e for e in edges if e["from_id"] in keep and e["to_id"] in keep],
        key=canonical,
    )
    return {"nodes": clean_nodes, "edges": clean_edges}


class Cache:
    def __init__(self, strategy, k=5):
        if strategy not in {"none", "fixed", "dependency"}:
            raise ValueError("unknown cache strategy")
        if k < 1:
            raise ValueError("k must be positive")
        self.strategy, self.k = strategy, k
        self.entries = {}

    def request(self, key, step, graph_input, compute):
        fingerprint = canonical(graph_input)
        old = self.entries.get(key)
        reuse = old is not None and self.strategy != "none"
        if reuse and self.strategy == "fixed":
            reuse = step - old[0] < self.k
        if reuse and self.strategy == "dependency":
            reuse = old[1] == fingerprint
        if reuse:
            return deepcopy(old[2]), True, 0.0
        value, latency = compute()
        self.entries[key] = (step, fingerprint, deepcopy(value))
        return value, False, latency


def equivalent(answer, gold):
    """Strict structured equality after case/whitespace normalization.

    No free-form semantic judge is claimed. Missing keys differ from null.
    """
    def norm(value):
        if isinstance(value, str):
            return " ".join(value.casefold().split())
        if isinstance(value, dict):
            return {key: norm(v) for key, v in value.items()}
        if isinstance(value, list):
            return [norm(v) for v in value]
        return value
    return norm(answer) == norm(gold)
