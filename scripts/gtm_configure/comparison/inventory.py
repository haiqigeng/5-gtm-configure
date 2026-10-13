"""Resolve preparation inventory into explicit reuse candidates."""

from copy import deepcopy

from gtm_configure.comparison.native import normalize_graph
from gtm_configure.core.model import IDENTITY_FIELDS
from gtm_configure.core.privacy import redact_for_persistence

INVENTORY_VERSION = "gtm-preparation-inventory@1"


def fill_reuse_candidates(request, inventory):
    """Fill only explicitly selected native bodies; never derive authority or policy."""
    if (
        inventory.get("schema_version") != INVENTORY_VERSION
        or inventory.get("purpose") != "preparation-only"
    ):
        raise ValueError("Expected a current preparation inventory")
    records = inventory.get("targets")
    if not isinstance(records, list) or len({t["target_id"] for t in records}) != len(records):
        raise ValueError("Inventory needs unique targets")
    result = deepcopy(request)
    targets = {t["target_id"]: t for t in result["targets"]}
    by_target = {t["target_id"]: t for t in records}
    for candidate in result.get("reuse_candidates", []):
        if "intended" in candidate:
            continue
        target_id = candidate.get("target_id")
        if target_id is None and len(targets) == 1:
            target_id = next(iter(targets))
        target, captured = targets.get(target_id), by_target.get(target_id)
        if (
            target is None
            or captured is None
            or any(target[f] != captured.get(f) for f in IDENTITY_FIELDS)
        ):
            raise ValueError("Reuse candidate inventory does not match the approved target")
        family, name = candidate["resource_family"], candidate["name"]
        receipt = captured.get("pagination", {}).get(family, {})
        if (
            receipt.get("exhausted") is not True
            or type(receipt.get("pages_read")) is not int
            or receipt["pages_read"] < 1
        ):
            raise ValueError("Reuse candidate family listing is incomplete")
        matches = [
            o
            for o in captured["objects"]
            if o.get("object_type") == family and o.get("name") == name
        ]
        if len(matches) != 1:
            raise ValueError("Reuse candidate must have exactly one inventory match")
        # Context resolves native IDs; all primary fields survive normalization.
        graph = {
            "objects": matches,
            "context_objects": [o for o in captured["objects"] if o is not matches[0]],
        }
        graph = redact_for_persistence(graph)
        normalized = normalize_graph(graph, target_types={target_id: target["container_type"]})
        native = next(iter(normalized.values()))
        if native.get("target_id") != target_id:
            raise ValueError("Inventory object is scoped to another target")
        candidate["intended"] = {
            k: v for k, v in native.items() if k not in {"target_id", "object_type", "name"}
        }
    return result
