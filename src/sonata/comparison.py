"""Ordinal comparison of complete execution events, without source locations."""

import json


def _semantic(event):
    # Preserve location-like user variable names. Strip provenance only at the
    # event root and in the standard error payload; bool and int stay distinct.
    value = {key: event.get(key) for key in ("kind", "depth", "function", "data", "variables", "stack")}
    if event.get("kind") == "error" and isinstance(value["data"], dict):
        value["data"] = {k: v for k, v in value["data"].items() if k not in {"line", "col"}}
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def compare_traces(left, right, window=4):
    """Find the first ordinal semantic divergence and return nearby events.

    This compares exact data/state/stack snapshots; it is not an edit-distance
    alignment or a proof of program equivalence. Source line/column shifts do
    not count as behavioral changes. IDs remain intact in returned windows.
    """
    if type(window) is not int or not 0 <= window <= 100:
        raise ValueError("window must be an integer from 0 through 100")
    if type(left) is not list or type(right) is not list or max(len(left), len(right)) > 100_000:
        raise ValueError("Comparison needs lists of at most 100000 events")
    if any(not isinstance(event, dict) for trace in (left, right) for event in trace):
        raise ValueError("Trace events must be objects")
    first = None
    for i in range(max(len(left), len(right))):
        if i >= min(len(left), len(right)) or _semantic(left[i]) != _semantic(right[i]):
            first = i
            break
    nearby = []
    if first is not None:
        for i in range(max(0, first-window), min(max(len(left), len(right)), first+window+1)):
            a, b = left[i] if i < len(left) else None, right[i] if i < len(right) else None
            nearby.append({"index": i, "left": a, "right": b,
                           "equal": a is not None and b is not None and _semantic(a) == _semantic(b)})
    return {"version": 1, "equal": first is None, "first_divergence": first,
            "left_length": len(left), "right_length": len(right), "window": nearby}
