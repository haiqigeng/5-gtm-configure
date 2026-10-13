"""Web inventory: shared across preparation and execution."""

from __future__ import annotations

from typing import Any

from gtm_configure.core.validation import (
    RunValidationError,
    _array,
    _exact_keys,
    _object,
    _optional_text,
    _text,
    _unique_texts,
)
from gtm_configure.domain.web_model import (
    INVENTORY_DISPOSITIONS,
)
from gtm_configure.domain.web_native import _effective_target


def _validate_inventory_dispositions(
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
    for index, item_raw in enumerate(_array(raw, "$.inventory_dispositions")):
        path = f"$.inventory_dispositions[{index}]"
        item = _object(item_raw, path)
        _exact_keys(
            item,
            path,
            required={
                "row_id",
                "source_order",
                "source_locator",
                "before_object_key",
                "before_tag_name",
                "disposition",
                "after_tag_name",
                "trigger_before",
                "trigger_after",
                "variable_changes",
                "parameter_changes",
                "consent_changes",
                "rationale",
                "operation_ids",
            },
        )
        row_id = _text(item.get("row_id"), f"{path}.row_id")
        if row_id in row_ids:
            raise RunValidationError(f"duplicate inventory row_id {row_id!r}")
        row_ids.add(row_id)
        order = item.get("source_order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 0:
            raise RunValidationError(f"{path}.source_order must be a non-negative integer")
        if order in orders:
            raise RunValidationError(f"duplicate inventory source_order {order}")
        orders.add(order)
        _text(item.get("source_locator"), f"{path}.source_locator")
        before_key = _optional_text(item.get("before_object_key"), f"{path}.before_object_key")
        before_name = _optional_text(item.get("before_tag_name"), f"{path}.before_tag_name")
        disposition = _text(item.get("disposition"), f"{path}.disposition")
        if disposition not in INVENTORY_DISPOSITIONS:
            raise RunValidationError(f"{path}.disposition has unsupported value {disposition!r}")
        after_name = _optional_text(item.get("after_tag_name"), f"{path}.after_tag_name")
        if disposition == "added":
            if before_key is not None or before_name is not None or after_name is None:
                raise RunValidationError(
                    f"{path}.added requires blank before identity and a non-empty after_tag_name"
                )
        else:
            if before_key is None or before_name is None:
                raise RunValidationError(
                    f"{path}.{disposition} requires before_object_key and before_tag_name"
                )
            if before_key in before_keys:
                raise RunValidationError(f"duplicate inventory before_object_key {before_key!r}")
            before_keys.add(before_key)
        if disposition == "remove" and after_name is not None:
            raise RunValidationError(f"{path}.remove requires a null after_tag_name")
        if disposition not in {"remove", "added"} and after_name is None:
            raise RunValidationError(f"{path}.{disposition} requires after_tag_name")
        if after_name is not None:
            if after_name in after_names:
                raise RunValidationError(f"duplicate inventory after_tag_name {after_name!r}")
            after_names.add(after_name)
        for field in (
            "trigger_before",
            "trigger_after",
            "variable_changes",
            "parameter_changes",
            "consent_changes",
        ):
            _unique_texts(item.get(field), f"{path}.{field}")
        _text(item.get("rationale"), f"{path}.rationale")
        linked_operations = set(_unique_texts(item.get("operation_ids"), f"{path}.operation_ids"))
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
        target = _effective_target(tag_operation, path) if disposition != "remove" else None
        target_name = target.get("name") if isinstance(target, dict) else None
        if disposition == "added":
            if after_name != target_name:
                raise RunValidationError(f"{path}.after_tag_name differs from the created tag")
        else:
            if before_key != tag_operation["object_key"]:
                raise RunValidationError(f"{path}.before_object_key differs from its tag operation")
            pre_change = _object(
                tag_operation.get("pre_change"), f"{path}.tag_operation.pre_change"
            )
            if before_name != pre_change.get("name"):
                raise RunValidationError(f"{path}.before_tag_name differs from pre_change.name")
            if disposition != "remove" and after_name != target_name:
                raise RunValidationError(f"{path}.after_tag_name differs from the target tag")
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
