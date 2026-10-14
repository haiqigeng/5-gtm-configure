"""Web execution: shared across preparation and execution."""

from __future__ import annotations

from typing import Any

import gtm_configure.core.validation as validation
import gtm_configure.domain.web_model as web_model
import gtm_configure.domain.web_native as web_native
from gtm_configure.core.model import CONSENT_MODES
from gtm_configure.core.schemas import validate_definition
from gtm_configure.core.validation import (
    RunValidationError,
    array,
    object,
    optional_text,
    text,
    unique_texts,
)
from gtm_configure.domain.consent import (
    validate_convention,
    validate_topology_consent_binding,
)
from gtm_configure.domain.localization import local_key, local_topology
from gtm_configure.domain.web_model import (
    BUILT_IN_TRIGGER_TYPES,
    LIFECYCLE_ROLES,
    NON_EXECUTING_TAG_ACTIONS,
    NORMAL_TRIGGER_ROLES,
    PAGE_LOAD_TRIGGER_TYPES,
    PAGE_VIEW_OCCURRENCES,
    PRE_CMP_POLICIES,
)
from gtm_configure.domain.web_native import (
    effective_target,
    resolved_trigger_types,
    semantic_trigger_reference,
    tag_additional_consent_checks,
    tag_firing_option,
    tag_trigger_references,
    trigger_filter_predicates,
)


def validate_normal_trigger_bindings(
    item: dict[str, Any],
    *,
    path: str,
    target: dict[str, Any],
    trigger_types: dict[str, str],
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw_trigger in enumerate(array(item.get("trigger_roles"), f"{path}.trigger_roles")):
        trigger_path = f"{path}.trigger_roles[{index}]"
        trigger = object(raw_trigger, trigger_path)
        object_key = semantic_trigger_reference(
            trigger.get("trigger_object_key"),
            f"{trigger_path}.trigger_object_key",
        )
        if object_key in seen:
            raise RunValidationError(f"{path}.trigger_roles contains duplicate {object_key!r}")
        seen.add(object_key)
        role = text(trigger.get("role"), f"{trigger_path}.role")
        if role not in NORMAL_TRIGGER_ROLES:
            raise RunValidationError(f"{trigger_path}.role has unsupported value {role!r}")
        trigger_type = trigger_types.get(object_key)
        actual_type = trigger_type
        if actual_type is None:
            raise RunValidationError(
                f"{trigger_path} references an unresolved trigger {object_key!r}"
            )
        if role == "cmp-readiness-grant" and trigger_type != "custom-event":
            raise RunValidationError(f"{trigger_path}.cmp-readiness-grant must be a Custom Event")
        if role == "initialization-page-load" and trigger_type not in PAGE_LOAD_TRIGGER_TYPES:
            raise RunValidationError(
                f"{trigger_path}.initialization-page-load uses an incompatible trigger type"
            )
        records.append({"trigger_object_key": object_key, "role": role})
    if not records:
        raise RunValidationError(f"{path}.trigger_roles must not be empty")
    intended_refs = set(tag_trigger_references(target, "firingTriggerId", f"{path}.bound_tag"))
    declared_refs = {item["trigger_object_key"] for item in records}
    if intended_refs != declared_refs:
        raise RunValidationError(
            f"{path}.trigger_roles must equal bound firingTriggerId; "
            f"missing={sorted(intended_refs - declared_refs)}, "
            f"extra={sorted(declared_refs - intended_refs)}"
        )
    return records


def _validate_trigger_consent_predicates(
    trigger_roles: list[dict[str, str]],
    blocking: list[str],
    operation_by_key: dict[str, dict[str, Any]],
    path: str,
) -> None:
    """Reject a repeated custom grant whose inverse is already an attached block.

    Filter rows are ANDed. A block with additional independent predicates is not the
    inverse of one firing condition. Shared business/host/environment filters can supply
    that context, but must never themselves be rejected merely for appearing in both.
    """
    by_trigger: dict[str, dict[tuple[str, bool], str]] = {}
    event_contexts: dict[str, set[tuple[str, bool]]] = {}
    for key in dict.fromkeys(
        [trigger["trigger_object_key"] for trigger in trigger_roles] + blocking
    ):
        if key in BUILT_IN_TRIGGER_TYPES:
            by_trigger[key] = {}
            event_contexts[key] = set()
            continue
        operation = operation_by_key.get(key)
        if operation is None or operation["object_type"] != "trigger":
            raise RunValidationError(f"{path} requires bound trigger snapshot for {key!r}")
        trigger_path = f"{path}.bound_trigger[{key!r}]"
        by_trigger[key], event_contexts[key] = trigger_filter_predicates(
            effective_target(operation, trigger_path), trigger_path
        )
    for trigger in trigger_roles:
        normal = by_trigger[trigger["trigger_object_key"]]
        for block_key in blocking:
            if not event_contexts[block_key] <= event_contexts[trigger["trigger_object_key"]]:
                # Do not remove a firing condition on the strength of an exception whose
                # event coverage is unproved. Exact lifecycle coverage remains a source/UI
                # review duty; this check does not infer arbitrary regex containment.
                continue
            block = by_trigger[block_key]
            for (signature, negate), normal_path in normal.items():
                inverse = (signature, not negate)
                if inverse in block and block.keys() - {inverse} <= normal.keys():
                    raise RunValidationError(
                        f"{path}: duplicated consent predicate between normal firing "
                        f"{normal_path} and blocking {block[inverse]}; "
                        "the attached block already owns this custom eligibility condition"
                    )


def validate_tag_policies(
    raw: Any,
    *,
    requirement_ids: set[str],
    operations: dict[str, dict[str, Any]],
    baseline_trigger_types: dict[str, str],
    transporter_tag_keys: set[str] | None = None,
    consent_by_id: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    transporter_tag_keys = set(transporter_tag_keys or set())
    operation_by_key = {item["object_key"]: item for item in operations.values()}
    trigger_types = resolved_trigger_types(operations, baseline_trigger_types)
    records: dict[str, dict[str, Any]] = {}
    for index, item_raw in enumerate(array(raw, "$.tag_policies")):
        path = f"$.tag_policies[{index}]"
        item = object(item_raw, path)
        validate_definition(
            item, "tagPolicy", lambda message: (_ for _ in ()).throw(RunValidationError(message))
        )
        tag_key = text(item.get("tag_object_key"), f"{path}.tag_object_key")
        if tag_key in records:
            raise RunValidationError(f"duplicate execution topology for {tag_key!r}")
        operation = operation_by_key.get(tag_key)
        if operation is None or operation["object_type"] != "tag":
            raise RunValidationError(f"{path}.tag_object_key must reference an in-scope tag")
        if operation["action"] in NON_EXECUTING_TAG_ACTIONS:
            raise RunValidationError(
                f"{path} must not assign target execution topology to {operation['action']!r}"
            )
        target = effective_target(operation, path)
        role = text(item.get("lifecycle_role"), f"{path}.lifecycle_role")
        if role not in LIFECYCLE_ROLES:
            raise RunValidationError(f"{path}.lifecycle_role has unsupported value {role!r}")
        policy = consent_by_id[item["consent_policy_id"]]
        mode = policy["consent_mode"]
        if mode not in CONSENT_MODES:
            raise RunValidationError(f"{path}.consent_mode has unsupported value {mode!r}")
        is_transporter = tag_key in transporter_tag_keys
        trigger_roles = validate_normal_trigger_bindings(
            item,
            path=path,
            target=target,
            trigger_types=trigger_types,
        )
        role_names = {trigger["role"] for trigger in trigger_roles}
        if role == "event-driven":
            if role_names != {"source-event"}:
                raise RunValidationError(
                    f"{path}.event-driven tags require only source-event triggers"
                )
            if any(
                trigger_types[trigger["trigger_object_key"]] in PAGE_LOAD_TRIGGER_TYPES
                for trigger in trigger_roles
            ):
                raise RunValidationError(
                    f"{path}.page-load trigger types require baseline-page-load lifecycle"
                )
        expected_baseline_roles = (
            {"cmp-readiness-grant"}
            if mode == "strict-basic"
            else {"initialization-page-load", "cmp-readiness-grant"}
        )
        if role == "baseline-page-load" and not expected_baseline_roles & role_names:
            raise RunValidationError(
                f"{path}.baseline-page-load under {mode} requires a {' or '.join(sorted(expected_baseline_roles))} trigger"
            )

        blocking = tag_trigger_references(target, "blockingTriggerId", f"{path}.bound_tag")
        for trigger_key in blocking:
            if trigger_types.get(trigger_key) != "custom-event":
                raise RunValidationError(
                    f"{path}.blocking_trigger_keys contains unresolved/non-Custom Event "
                    f"{trigger_key!r}"
                )
        block_scope = optional_text(
            item.get("blocking_event_scope"),
            f"{path}.blocking_event_scope",
        )
        additional = tag_additional_consent_checks(target, f"{path}.bound_tag")
        if mode == "strict-basic":
            convention = policy["web_enforcement"]["mechanism"]
            alternative = convention in {
                "firing-trigger-condition",
                "additional-consent-checks",
            }
            if is_transporter and (blocking or block_scope):
                raise RunValidationError(
                    f"{path} transporter tags must not inherit destination vendor blocks"
                )
            if not is_transporter and not alternative and (not blocking or not block_scope):
                raise RunValidationError(
                    f"{path}.strict-basic requires blocking_trigger_keys and blocking_event_scope"
                )
            if additional and convention != "additional-consent-checks":
                raise RunValidationError(
                    f"{path}.additional_consent_checks must be empty under strict-basic"
                )
            if blocking:
                _validate_trigger_consent_predicates(
                    trigger_roles, blocking, operation_by_key, path
                )
        elif blocking or block_scope or additional:
            raise RunValidationError(
                f"{path}.{mode} must not carry a defeating block or Additional check"
            )
        tag_firing_option(target, f"{path}.bound_tag")
        may_precede_cmp = item["pre_cmp_policy"] != "not-applicable"
        if mode == "client-policy-ungated" and may_precede_cmp:
            raise RunValidationError(f"{path}.client-policy-ungated requires a non-CMP lifecycle")
        pre_cmp_policy = text(item.get("pre_cmp_policy"), f"{path}.pre_cmp_policy")
        if pre_cmp_policy not in PRE_CMP_POLICIES:
            raise RunValidationError(
                f"{path}.pre_cmp_policy has unsupported value {pre_cmp_policy!r}"
            )
        if may_precede_cmp and role != "event-driven":
            raise RunValidationError(f"{path}.may_precede_cmp applies only to event-driven tags")
        if may_precede_cmp and pre_cmp_policy == "not-applicable":
            raise RunValidationError(
                f"{path}.pre_cmp_policy must resolve an event that may precede CMP"
            )
        if not may_precede_cmp and pre_cmp_policy != "not-applicable":
            raise RunValidationError(
                f"{path}.pre_cmp_policy must be not-applicable when may_precede_cmp is false"
            )
        page_view_occurrences = unique_texts(
            item.get("page_view_occurrences", []), f"{path}.page_view_occurrences"
        )
        if set(page_view_occurrences) - PAGE_VIEW_OCCURRENCES:
            raise RunValidationError(f"{path}.page_view_occurrences contains unsupported values")
        unique_texts(item.get("evidence"), f"{path}.evidence", allow_empty=False)
        records[tag_key] = item
    return records


def validate_target_execution(
    *,
    local_operations,
    consent_by_id,
    fail,
    non_consent_requirement_ids,
    operations,
    requirement_by_id,
    requirement_ids,
    target_id,
    topologies_by_target,
    transporter_keys,
):
    local_topologies = []
    for index, topology in enumerate(topologies_by_target[target_id]):
        path = f"$.tag_policies[{index}]"
        validate_topology_consent_binding(
            topology,
            consent_by_id=consent_by_id,
            path=path,
            fail=fail,
            transporter_keys=transporter_keys,
        )
        local_topologies.append(local_topology(topology, target_id, path, fail))
        enforcement = consent_by_id[topology["consent_policy_id"]]["web_enforcement"]
        validate_convention(
            topology, enforcement, {item["object_key"]: item for item in operations}, fail
        )
    try:
        validated_topologies = validate_tag_policies(
            local_topologies,
            requirement_ids=set(requirement_ids),
            operations=local_operations,
            baseline_trigger_types={},
            consent_by_id=consent_by_id,
            transporter_tag_keys={
                local_key(
                    value,
                    target_id,
                    "$.consent_policies[].transporter_tag_keys",
                    fail,
                )
                for value in transporter_keys
                if value.startswith(f"{target_id}::")
            },
        )
    except validation.RunValidationError as exc:
        fail(str(exc))
        return

    executable_tags = {
        item["object_key"]
        for item in local_operations.values()
        if item["object_type"] == "tag"
        and item["action"] not in web_model.NON_EXECUTING_TAG_ACTIONS
        and set(item.get("requirement_ids", [])) & non_consent_requirement_ids
    }
    if set(validated_topologies) != executable_tags:
        missing = sorted(executable_tags - set(validated_topologies))
        extra = sorted(set(validated_topologies) - executable_tags)
        fail(
            f"web target {target_id!r} needs exactly one execution topology per executing "
            f"tag; missing={missing}, extra={extra}"
        )

    for topology in validated_topologies.values():
        operation = next(
            item
            for item in local_operations.values()
            if item["object_key"] == topology["tag_object_key"]
        )
        target = web_native.effective_target(operation, "$.tag_policies[].bound_tag")
        tag_type = web_native.tag_type(target, "$.tag_policies[].bound_tag")
        if (
            topology["lifecycle_role"] == "event-driven"
            and tag_type in web_model.GA4_EVENT_TAG_TYPES
        ):
            approved_names = {
                requirement_by_id[requirement_id].get("event_name")
                for requirement_id in operation.get("requirement_ids", [])
                if requirement_id in requirement_by_id
            } - {None}
            present, configured_name = web_native.configuration_value(
                target, {"event_name", "eventName"}
            )
            if approved_names and (
                len(approved_names) != 1 or not present or configured_name not in approved_names
            ):
                fail(
                    f"GA4 event tag {operation['object_key']!r} eventName must equal its "
                    f"single approved event name; approved={sorted(approved_names)}"
                )
    return validated_topologies
