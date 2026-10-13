"""Read-only preparation inventory through the same authenticated GTM adapter."""

from datetime import datetime, timezone

from gtm_configure.adapters.mcp import FAMILIES, McpTargetAdapter
from gtm_configure.comparison.inventory import IDENTITY_FIELDS, INVENTORY_VERSION
from gtm_configure.comparison.native import (
    BUILT_IN_TRIGGER_IDS,
    ID_FIELDS,
    REFERENCE_FIELDS,
)
from gtm_configure.core.json_io import write_json_atomic
from gtm_configure.core.privacy import redact_for_persistence
from gtm_configure.domain.targets import validate_targets
from gtm_configure.runtime.adapter_protocol import (
    AdapterExecutionError,
    collect_paginated_with_receipt,
)


def discovery_targets(request):
    if not isinstance(request, dict) or set(request) != {
        "mode",
        "targets",
        "resource_families",
    }:
        raise ValueError(
            "Discovery input needs mode, approved targets and selected resource_families"
        )
    if request["mode"] not in {"web", "server", "pipeline"}:
        raise ValueError("Unsupported discovery mode")
    targets = list(validate_targets(request["targets"], request["mode"]).values())
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
    inventory = {
        "schema_version": INVENTORY_VERSION,
        "targets": [],
        "purpose": "preparation-only",
    }
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
