"""Cache dependencies describe query input, including absent edges and objects."""
from copy import deepcopy
import json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def projection(graph, kind, target=None, granularity="fine", course_semantics=False):
    """Project query dependencies, including absent nodes and newly added edges.

    course_semantics preserves edge order and bidirectional IN dependencies,
    matching the original course annotation protocol. The legacy baseline uses
    sorted edges and directed IN traversal.

    Fine location input follows IN/ON ancestors and reverse HOLDS edges. Summary
    consumes the entire graph. Coarse deliberately uses the entire graph for both:
    this is a conservative baseline, not the teacher package's room-only policy.
    """
    if kind not in {"location", "summary"}:
        raise ValueError("unknown query kind")
    if granularity not in {"fine", "coarse"}:
        raise ValueError("unknown dependency granularity")
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
                if (course_semantics and rel == "IN" and b in keep
                        and nodes.get(b, {}).get("category") != "Rooms"):
                    extra.add(a)
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
                node[field] = (list(node.get(field, [])) if course_semantics else sorted(node.get(field, [])))
            clean_nodes.append(node)
    clean_edges = [e for e in edges if e["from_id"] in keep and e["to_id"] in keep]
    if not course_semantics:
        clean_edges = sorted(clean_edges, key=canonical)
    return {"nodes": clean_nodes, "edges": clean_edges}


class Cache:
    def __init__(self, strategy, k=5):
        if strategy not in {"none", "fixed", "dependency"}:
            raise ValueError("unknown cache strategy")
        if k < 1:
            raise ValueError("k must be positive")
        self.strategy, self.k = strategy, k
        self.entries = {}

    def clear(self):
        self.entries.clear()

    def store(self, key, step, fingerprint, value):
        if not isinstance(value, dict):
            raise ValueError("only structured successful answers can be cached")
        self.entries[key] = (step, fingerprint, deepcopy(value))

    def decision(self, key, step, graph_input):
        fingerprint = canonical(graph_input)
        old = self.entries.get(key)
        if old is None:
            return False, "miss", fingerprint
        if self.strategy == "none":
            return False, "always_recompute", fingerprint
        if self.strategy == "fixed":
            reuse = step - old[0] < self.k
            return reuse, "ttl_valid" if reuse else "ttl_expired", fingerprint
        reuse = old[1] == fingerprint
        return reuse, "dependencies_unchanged" if reuse else "dependencies_changed", fingerprint

    def request(self, key, step, graph_input, compute):
        reuse, _, fingerprint = self.decision(key, step, graph_input)
        old = self.entries.get(key)
        if reuse:
            return deepcopy(old[2]), True, 0.0
        value, latency = compute()
        self.store(key, step, fingerprint, value)
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
