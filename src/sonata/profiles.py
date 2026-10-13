"""Versioned, serializable listening profiles. Filtering never compresses time."""

import math
from collections.abc import Mapping


PROFILE_VERSION = 1
_FIELDS = {"version", "mapping", "event_kinds", "functions", "variables", "ranges", "event_stride"}


def validate_profile(profile=None):
    """Return a fresh normalized profile; omitted fields have stable defaults.

    An absent profile selects the original mapping for artifact compatibility.
    An explicit object (even {}) selects the semantic mapping by default.
    Empty filter lists mute all events; null lists impose no restriction.
    """
    legacy = profile is None
    if legacy:
        profile = {}
    if not isinstance(profile, Mapping) or set(profile) - _FIELDS:
        raise ValueError("Profile must be an object with documented profile fields")
    version = profile.get("version", PROFILE_VERSION)
    if type(version) is not int or version != PROFILE_VERSION:
        raise ValueError("Unsupported profile version; expected 1")
    mapping = profile.get("mapping", "legacy" if legacy else "semantic")
    if mapping not in ("legacy", "semantic"):
        raise ValueError("Profile mapping must be legacy or semantic")
    stride = profile.get("event_stride", .25)
    if type(stride) not in (int, float) or not math.isfinite(stride) or not 1/32 <= stride <= 4:
        raise ValueError("event_stride must be finite and between 1/32 and 4 beats")
    result = {"version": version, "mapping": mapping, "event_stride": float(stride)}
    for field in ("event_kinds", "functions", "variables"):
        value = profile.get(field)
        if value is not None:
            if type(value) is not list or len(value) > 256 or any(type(v) is not str or not 1 <= len(v) <= 128 for v in value):
                raise ValueError(f"{field} must be null or a list of at most 256 nonempty names")
            value = sorted(set(value))
        result[field] = value
    ranges = profile.get("ranges", {})
    if not isinstance(ranges, Mapping) or len(ranges) > 256:
        raise ValueError("ranges must be an object with at most 256 variable ranges")
    result["ranges"] = {}
    for name, bounds in ranges.items():
        if type(name) is not str or not 1 <= len(name) <= 128 or type(bounds) not in (list, tuple) or len(bounds) != 2:
            raise ValueError("Each range must map a name to [minimum, maximum]")
        low, high = bounds
        if any(type(v) is not int or not -(2**63) <= v < 2**63 for v in bounds) or low >= high:
            raise ValueError("Range endpoints must be signed 64-bit integers, minimum < maximum")
        result["ranges"][name] = [low, high]
    return result


def event_selected(event, previous_variables, profile):
    """Match intersecting filters, including mutation of watched snapshots."""
    data = event.get("data") or {}
    if profile["event_kinds"] is not None and event.get("kind") not in profile["event_kinds"]:
        return False
    if profile["functions"] is not None and event.get("function") not in profile["functions"]:
        return False
    if profile["variables"] is not None:
        missing = object()
        variables = event.get("variables") or {}
        tagged = data.get("name") in profile["variables"] and not data.get("function") and event.get("kind") != "call"
        changed = any(variables.get(name, missing) != previous_variables.get(name, missing)
                      for name in profile["variables"])
        if not tagged and not changed:
            return False
    return True
