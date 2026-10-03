"""Read-only preparation inventory through the same authenticated GTM adapter."""

from copy import deepcopy
from datetime import datetime, timezone

from adapter_support import AdapterExecutionError, collect_paginated_with_receipt
from diff_object_graph import BUILT_IN_TRIGGER_IDS, ID_FIELDS, REFERENCE_FIELDS, normalize_graph
from mcp_adapter import FAMILIES, McpTargetAdapter
from redaction import redact_for_persistence
from strict_json import write_json_atomic
from validate_configuration_contract import _validate_targets

INVENTORY_VERSION = "gtm-preparation-inventory@1"
IDENTITY_FIELDS = ("account_id", "container_id", "workspace_id", "container_type")


def discovery_targets(request):
    if not isinstance(request, dict) or set(request) != {"mode", "targets", "resource_families"}:
        raise ValueError(
            "Discovery input needs mode, approved targets and selected resource_families"
        )
    if request["mode"] not in {"web", "server", "pipeline"}:
        raise ValueError("Unsupported discovery mode")
    targets = list(_validate_targets(request["targets"], request["mode"]).values())
    selected = request["resource_families"]
    if not isinstance(selected, dict) or set(selected) != {t["target_id"] for t in targets}:
        raise ValueError("resource_families must select each approved target")
    for families in selected.values():
        if (
            not isinstance(families, list)
            or not families
            or any(not isinstance(f, str) or f not in FAMILIES for f in families)
            or len(set(families)) != len(families)
        ):
            raise ValueError("resource_families needs unique supported families")
    return targets


def discover(request, profiles, transport, output):
    targets = discovery_targets(request)

    def read_only(tool, arguments):
        family = tool.split("__")[-1]
        actions = (
            {"get", "list"}
            if family in {value[0] for value in FAMILIES.values()}
            else (
                {"get", "getStatus"}
                if family == "gtm_workspace"
                else ({"get"} if family == "gtm_container" else set())
            )
        )
        if arguments.get("action") not in actions:
            raise AdapterExecutionError("Preparation discovery forbids mutations")
        return transport(tool, arguments)

    # Validate all selected profiles before the first remote read.
    adapters = [McpTargetAdapter(t, profiles.get(t["target_id"], {}), read_only) for t in targets]
    inventory = {"schema_version": INVENTORY_VERSION, "targets": [], "purpose": "preparation-only"}
    for target, adapter in zip(targets, adapters, strict=True):
        expected = {field: target[field] for field in IDENTITY_FIELDS}
        if adapter.identity() != expected:
            raise AdapterExecutionError(
                "Discovery authenticated identity differs from approved target"
            )
        objects, receipts = [], {}
        pending = set(request["resource_families"][target["target_id"]])
        # A preparation variable inventory needs its consumer and sensitive-reference closure.
        if "variable" in pending:
            pending.add("tag")
        while pending:
            family = sorted(pending)[0]
            pending.remove(family)
            if family in receipts:
                continue
            if not adapter.capabilities().get(family, {}).get("list"):
                raise AdapterExecutionError(f"Required discovery family {family!r} is unavailable")
            items, receipts[family] = collect_paginated_with_receipt(
                lambda cursor, selected=family: adapter.list_resource_page(selected, cursor)
            )
            objects.extend(
                {**item, "target_id": target["target_id"], "object_type": family} for item in items
            )
            for item in items:
                for field, identifier in REFERENCE_FIELDS.items():
                    values = item.get(field, [])
                    values = values if isinstance(values, list) else [values]
                    if values and not (
                        identifier == "triggerId"
                        and all(str(v) in BUILT_IN_TRIGGER_IDS for v in values)
                    ):
                        pending.add(ID_FIELDS[identifier])
                if item.get("setupTag") or item.get("teardownTag"):
                    pending.add("tag")
                if str(item.get("type", "")).startswith("cvt_"):
                    pending.add("template")

                def has_reference(value):
                    if isinstance(value, str):
                        return "{{" in value and "}}" in value
                    if isinstance(value, dict):
                        return any(has_reference(v) for v in value.values())
                    return isinstance(value, list) and any(has_reference(v) for v in value)

                if has_reference(item):
                    pending.add("variable")
            pending.difference_update(receipts)
        if not receipts:
            raise AdapterExecutionError("Discovery needs at least one list capability")
        changes, receipts["workspace_changes"] = collect_paginated_with_receipt(
            adapter.list_workspace_changes_page
        )
        if adapter.identity() != expected:
            raise AdapterExecutionError("Discovery identity changed during collection")
        # Scan the complete graph before persistence, including cross-object taint.
        safe = redact_for_persistence({"objects": objects, "workspace_changes": changes})
        inventory["targets"].append(
            {
                "target_id": target["target_id"],
                **expected,
                **safe,
                "pagination": receipts,
            }
        )
    inventory["captured_at"] = datetime.now(timezone.utc).isoformat()
    write_json_atomic(output, inventory)
    return {
        "status": "Discovered",
        "writes_attempted": 0,
        "targets": [
            {
                "target_id": t["target_id"],
                "objects": len(t["objects"]),
                "families": list(t["pagination"]),
            }
            for t in inventory["targets"]
        ],
        "next_action": "Inspect inventory; select reuse candidates and supply policy/evidence in the request. Execution captures a fresh baseline.",
    }


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
