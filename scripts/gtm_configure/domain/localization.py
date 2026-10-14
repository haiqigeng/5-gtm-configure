"""Project target-scoped identities into native web validation views."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from gtm_configure.core.model import BUILT_IN_TRIGGER_IDS
from gtm_configure.core.validation import array as local_array
from gtm_configure.core.validation import text as local_text


def local_key(value: Any, target_id: str, path: str, fail: Callable[[str], None]) -> str:
    key = local_text(value, path, error_type=fail)
    prefix = f"{target_id}::"
    if not key.startswith(prefix):
        fail(f"{path} must reference target {target_id!r}")
        return key
    return key[len(prefix) :]


def local_trigger_reference(
    value: Any, target_id: str, path: str, fail: Callable[[str], None]
) -> str:
    reference = local_text(value, path, error_type=fail)
    if reference in BUILT_IN_TRIGGER_IDS:
        return reference
    return local_key(reference, target_id, path, fail)


def local_target(
    raw: Any, target_id: str, path: str, fail: Callable[[str], None]
) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        fail(f"{path} must be an object")
        return None
    target = deepcopy(raw)
    for field in ("firingTriggerId", "blockingTriggerId"):
        if field not in target:
            continue
        values = local_array(target[field], f"{path}.{field}", error_type=fail)
        target[field] = [
            local_trigger_reference(item, target_id, f"{path}.{field}[]", fail) for item in values
        ]
    return target


def localize_operations(
    operations: list[dict[str, Any]], target_id: str, fail: Callable[[str], None]
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(operations):
        if source.get("target_id") != target_id:
            continue
        path = f"$.implementation.objects[{index}]"
        record = deepcopy(source)
        record["operation_id"] = source["operation_id"]
        record["object_type"] = source["resource_family"]
        record["object_key"] = local_key(source["object_key"], target_id, path, fail)
        record["dependencies"] = source["dependencies"]
        record["intended"] = local_target(
            source.get("intended"), target_id, f"{path}.intended", fail
        )
        # Intended references use target-scoped semantic keys.  Pre-change is an
        # authoritative GTM snapshot and therefore keeps native resource IDs.
        record["pre_change"] = deepcopy(source.get("pre_change"))
        for snapshot_name in ("intended", "pre_change"):
            snapshot = record.get(snapshot_name)
            if isinstance(snapshot, dict):
                snapshot.setdefault("object_type", record["object_type"])
                snapshot.setdefault(
                    "name",
                    source.get("new_name", source["name"])
                    if snapshot_name == "intended"
                    else source["name"],
                )
        output[record["operation_id"]] = record
    return output


def local_topology(
    source: dict[str, Any], target_id: str, path: str, fail: Callable[[str], None]
) -> dict[str, Any]:
    record = deepcopy(source)
    record["tag_object_key"] = local_key(
        source.get("tag_object_key"), target_id, f"{path}.tag_object_key", fail
    )
    for index, trigger in enumerate(record.get("trigger_roles", [])):
        trigger["trigger_object_key"] = local_trigger_reference(
            trigger.get("trigger_object_key"),
            target_id,
            f"{path}.trigger_roles[{index}].trigger_object_key",
            fail,
        )
    return record


def local_page_decision(
    source: dict[str, Any], target_id: str, path: str, fail: Callable[[str], None]
) -> dict[str, Any]:
    record = deepcopy(source)
    record.pop("target_id", None)
    for field in ("owner_object_key", "google_tag_object_key"):
        if record.get(field) is not None:
            record[field] = local_key(record[field], target_id, f"{path}.{field}", fail)
    return record


def local_first_party_route(
    source: dict[str, Any], target_id: str, path: str, fail: Callable[[str], None]
) -> dict[str, Any]:
    record = deepcopy(source)
    record["consumer_object_keys"] = [
        local_key(value, target_id, f"{path}.consumer_object_keys[]", fail)
        for value in record.get("consumer_object_keys", [])
    ]
    for index, binding in enumerate(record.get("consumer_bindings", [])):
        binding["object_key"] = local_key(
            binding.get("object_key"),
            target_id,
            f"{path}.consumer_bindings[{index}].object_key",
            fail,
        )
    return record


def web_sections_by_target(
    sections: list[dict[str, Any]], field: str, web_target_ids: set[str]
) -> dict[str, list[dict[str, Any]]]:
    output = {target_id: [] for target_id in web_target_ids}
    for source in sections:
        key = source.get(field)
        if not isinstance(key, str):
            continue
        target_id = key.split("::", 1)[0]
        if target_id in output:
            output[target_id].append(source)
    return output
