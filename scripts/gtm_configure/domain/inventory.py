"""Web inventory: shared across preparation and execution."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import gtm_configure.core.validation as validation
from gtm_configure.core.validation import (
    RunValidationError,
    array,
    object,
    text,
    unique_texts,
)
from gtm_configure.domain.localization import local_key
from gtm_configure.domain.native import (
    variable_consumers,
)
from gtm_configure.domain.resources import requires_variable_consumer_check
from gtm_configure.domain.web_model import (
    INVENTORY_DISPOSITIONS,
)
from gtm_configure.domain.web_native import effective_target


def validate_inventory_dispositions(
    raw: Any,
    *,
    execution_mode: str,
    in_scope_tag_keys: set[str],
    operations: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    allowed_tag_actions = {
        "added": {"create"},
        "keep": {"reuse", "untouched"},
        "update": {"update", "rename", "unpause"},
        "remap": {"update", "rename"},
        "pause": {"pause"},
        "remove": {"remove"},
        "replace": {"replace"},
        "supersede": {"pause", "reuse", "untouched"},
    }
    operation_ids = set(operations)
    row_ids: set[str] = set()
    orders: set[int] = set()
    before_keys: set[str] = set()
    after_names: set[str] = set()
    linked_tag_operation_ids: set[str] = set()
    records: list[dict[str, Any]] = []
    for index, item_raw in enumerate(array(raw, "$.inventory_dispositions")):
        path = f"$.inventory_dispositions[{index}]"
        item = object(item_raw, path)
        row_id = text(item.get("row_id"), f"{path}.row_id")
        if row_id in row_ids:
            raise RunValidationError(f"duplicate inventory row_id {row_id!r}")
        row_ids.add(row_id)
        order = item.get("source_order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 0:
            raise RunValidationError(f"{path}.source_order must be a non-negative integer")
        if order in orders:
            raise RunValidationError(f"duplicate inventory source_order {order}")
        orders.add(order)
        text(item.get("source_locator"), f"{path}.source_locator")
        disposition = text(item.get("disposition"), f"{path}.disposition")
        if disposition not in INVENTORY_DISPOSITIONS:
            raise RunValidationError(f"{path}.disposition has unsupported value {disposition!r}")
        text(item.get("rationale"), f"{path}.rationale")
        linked_operations = set(unique_texts(item.get("operation_ids"), f"{path}.operation_ids"))
        if linked_operations - operation_ids:
            raise RunValidationError(f"{path}.operation_ids contains unknown IDs")
        tag_operations = [
            operations[operation_id]
            for operation_id in linked_operations
            if operations[operation_id]["object_type"] == "tag"
        ]
        if len(tag_operations) != 1:
            raise RunValidationError(f"{path}.operation_ids must link exactly one tag operation")
        tag_operation = tag_operations[0]
        operation_id = tag_operation["operation_id"]
        if operation_id in linked_tag_operation_ids:
            raise RunValidationError(
                f"tag operation {operation_id!r} is linked by multiple inventory rows"
            )
        linked_tag_operation_ids.add(operation_id)
        if tag_operation["action"] not in allowed_tag_actions[disposition]:
            raise RunValidationError(
                f"{path}.{disposition} is incompatible with tag action {tag_operation['action']!r}"
            )
        if item["target_id"] != tag_operation["target_id"]:
            raise RunValidationError(f"{path}.target_id must select the linked tag target")
        if disposition != "added":
            before_key = tag_operation["object_key"]
            if before_key in before_keys:
                raise RunValidationError(f"duplicate inventory source tag {before_key!r}")
            before_keys.add(before_key)
            object(tag_operation.get("pre_change"), f"{path}.tag_operation.pre_change")
        if disposition != "remove":
            target_name = effective_target(tag_operation, path).get("name")
            if target_name in after_names:
                raise RunValidationError(f"duplicate inventory target tag name {target_name!r}")
            after_names.add(target_name)
        records.append(item)
    if execution_mode == "refonte-durable" and before_keys != in_scope_tag_keys:
        missing = sorted(in_scope_tag_keys - before_keys)
        extra = sorted(before_keys - in_scope_tag_keys)
        raise RunValidationError(
            "refonte inventory dispositions must cover every in-scope baseline tag exactly; "
            f"missing={missing}, extra={extra}"
        )
    if execution_mode == "refonte-durable":
        tag_operation_ids = {
            operation_id
            for operation_id, operation in operations.items()
            if operation["object_type"] == "tag"
        }
        if tag_operation_ids != linked_tag_operation_ids:
            missing = sorted(tag_operation_ids - linked_tag_operation_ids)
            extra = sorted(linked_tag_operation_ids - tag_operation_ids)
            raise RunValidationError(
                "refonte inventory rows must cover every tag operation exactly; "
                f"missing={missing}, extra={extra}"
            )
        existing_orders = [
            item["source_order"] for item in records if item["disposition"] != "added"
        ]
        added_orders = [item["source_order"] for item in records if item["disposition"] == "added"]
        if existing_orders and added_orders and min(added_orders) <= max(existing_orders):
            raise RunValidationError("refonte added inventory rows must follow all source rows")
    return records


def validate_shared_variable_consumers(
    *, local_operations, baseline_resources, fail, operations_by_key, target_id
):
    if baseline_resources is not None:
        target_baseline = baseline_resources.get(target_id, {})
        baseline_tags = target_baseline.get("tag", [])
        for operation in local_operations.values():
            if not requires_variable_consumer_check(operation):
                continue
            consumers = {
                f"tag::{name}"
                for name in variable_consumers(
                    operation, baseline_tags, target_baseline.get("variable", [])
                )
            }
            missing_consumers = sorted(consumers - set(operations_by_key))
            if missing_consumers:
                fail(
                    f"shared variable mutation {operation['object_key']!r} "
                    "does not include every authenticated baseline consumer: "
                    + ", ".join(missing_consumers)
                )


def validate_target_inventory(
    *,
    local_operations,
    baseline_in_scope_tags,
    execution_mode,
    fail,
    inventory_dispositions,
    target_id,
):
    local_inventory = []
    for index, row in enumerate(inventory_dispositions):
        if not isinstance(row, dict):
            continue
        local_ids = [value for value in row["operation_ids"] if value in local_operations]
        if not local_ids:
            continue
        record = deepcopy(row)
        record.pop("operation_keys", None)
        record["operation_ids"] = local_ids
        local_inventory.append(record)
    local_scope = (
        {
            local_key(
                value,
                target_id,
                "$.container_baselines[].resource_identities.tag",
                fail,
            )
            for value in baseline_in_scope_tags.get(target_id, set())
        }
        if baseline_in_scope_tags is not None
        else {
            item["object_key"]
            for item in local_operations.values()
            if item["object_type"] == "tag" and item["action"] != "create"
        }
    )
    try:
        validate_inventory_dispositions(
            local_inventory,
            execution_mode=execution_mode,
            in_scope_tag_keys=local_scope,
            operations=local_operations,
        )
    except validation.RunValidationError as exc:
        fail(str(exc))
        return
