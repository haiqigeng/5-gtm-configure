"""Web execution: shared across preparation and execution."""

from __future__ import annotations

from typing import Any

import gtm_configure.core.validation as validation
import gtm_configure.domain.web_model as web_model
import gtm_configure.domain.web_native as web_native
from gtm_configure.core.model import CONSENT_MODES
from gtm_configure.core.validation import (
    RunValidationError,
    array,
    object,
    optional_text,
    text,
    unique_texts,
)
from gtm_configure.domain.consent import (
    ALTERNATIVE_GATES,
    validate_convention,
    validate_topology_consent_binding,
)
from gtm_configure.domain.localization import local_key, local_topology
from gtm_configure.domain.web_model import (
    BUILT_IN_TRIGGER_TYPES,
    ECOMMERCE_ROUTES,
    FIRING_OPTIONS,
    GA4_EVENT_TAG_TYPES,
    GOOGLE_ADS_CONVERSION_TAG_TYPES,
    GOOGLE_CONFIGURATION_TAG_TYPES,
    LIFECYCLE_ROLES,
    NON_EXECUTING_TAG_ACTIONS,
    NORMAL_TRIGGER_ROLES,
    NORMAL_TRIGGER_TYPES,
    PAGE_LOAD_TRIGGER_TYPES,
    PAGE_VIEW_OCCURRENCES,
    PRE_CMP_POLICIES,
)
from gtm_configure.domain.web_native import (
    effective_target,
    resolved_trigger_types,
    semantic_trigger_reference,
    semantic_trigger_references,
    tag_additional_consent_checks,
    tag_firing_option,
    tag_trigger_references,
    tag_type,
    trigger_filter_predicates,
)

_GOOGLE_NATIVE_CONSENT_TAG_TYPES = (
    GOOGLE_CONFIGURATION_TAG_TYPES
    | GA4_EVENT_TAG_TYPES
    | GOOGLE_ADS_CONVERSION_TAG_TYPES
    | {"sp", "flc", "fls", "gclidw"}
)


_GOOGLE_NATIVE_CONSENT_TYPES = {
    "ad_storage",
    "analytics_storage",
    "ad_user_data",
    "ad_personalization",
}


def validate_normal_trigger_bindings(
    item: dict[str, Any],
    *,
    path: str,
    target: dict[str, Any],
    trigger_types: dict[str, str],
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw_trigger in enumerate(
        array(item.get("normal_triggers"), f"{path}.normal_triggers")
    ):
        trigger_path = f"{path}.normal_triggers[{index}]"
        trigger = object(raw_trigger, trigger_path)
        object_key = semantic_trigger_reference(
            trigger.get("trigger_object_key"),
            f"{trigger_path}.trigger_object_key",
        )
        if object_key in seen:
            raise RunValidationError(f"{path}.normal_triggers contains duplicate {object_key!r}")
        seen.add(object_key)
        role = text(trigger.get("role"), f"{trigger_path}.role")
        if role not in NORMAL_TRIGGER_ROLES:
            raise RunValidationError(f"{trigger_path}.role has unsupported value {role!r}")
        trigger_type = text(trigger.get("type"), f"{trigger_path}.type")
        if trigger_type not in NORMAL_TRIGGER_TYPES:
            raise RunValidationError(f"{trigger_path}.type has unsupported value {trigger_type!r}")
        actual_type = trigger_types.get(object_key)
        if actual_type is None:
            raise RunValidationError(
                f"{trigger_path} references an unresolved trigger {object_key!r}"
            )
        if trigger_type != actual_type:
            raise RunValidationError(
                f"{trigger_path}.type {trigger_type!r} differs from bound trigger type {actual_type!r}"
            )
        if role == "cmp-readiness-grant" and trigger_type != "custom-event":
            raise RunValidationError(f"{trigger_path}.cmp-readiness-grant must be a Custom Event")
        if role == "initialization-page-load" and trigger_type not in PAGE_LOAD_TRIGGER_TYPES:
            raise RunValidationError(
                f"{trigger_path}.initialization-page-load uses an incompatible trigger type"
            )
        records.append({"trigger_object_key": object_key, "role": role, "type": trigger_type})
    if not records:
        raise RunValidationError(f"{path}.normal_triggers must not be empty")
    intended_refs = set(tag_trigger_references(target, "firingTriggerId", f"{path}.bound_tag"))
    declared_refs = {item["trigger_object_key"] for item in records}
    if intended_refs != declared_refs:
        raise RunValidationError(
            f"{path}.normal_triggers must equal bound firingTriggerId; "
            f"missing={sorted(intended_refs - declared_refs)}, "
            f"extra={sorted(declared_refs - intended_refs)}"
        )
    return records


def _validate_trigger_consent_predicates(
    normal_triggers: list[dict[str, str]],
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
        [trigger["trigger_object_key"] for trigger in normal_triggers] + blocking
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
    for trigger in normal_triggers:
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


def validate_execution_topologies(
    raw: Any,
    *,
    requirement_ids: set[str],
    operations: dict[str, dict[str, Any]],
    baseline_trigger_types: dict[str, str],
    transporter_tag_keys: set[str] | None = None,
    consent_enforcements: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    transporter_tag_keys = set(transporter_tag_keys or set())
    operation_by_key = {item["object_key"]: item for item in operations.values()}
    trigger_types = resolved_trigger_types(operations, baseline_trigger_types)
    records: dict[str, dict[str, Any]] = {}
    for index, item_raw in enumerate(array(raw, "$.execution_topologies")):
        path = f"$.execution_topologies[{index}]"
        item = object(item_raw, path)
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
        linked = set(
            unique_texts(
                item.get("requirement_ids"),
                f"{path}.requirement_ids",
                allow_empty=False,
            )
        )
        if linked - requirement_ids:
            raise RunValidationError(f"{path}.requirement_ids contains unknown IDs")
        if linked != set(operation["requirement_ids"]):
            raise RunValidationError(
                f"{path}.requirement_ids must equal the tag operation requirement_ids"
            )
        role = text(item.get("lifecycle_role"), f"{path}.lifecycle_role")
        if role not in LIFECYCLE_ROLES:
            raise RunValidationError(f"{path}.lifecycle_role has unsupported value {role!r}")
        mode = text(item.get("consent_mode"), f"{path}.consent_mode")
        if mode not in CONSENT_MODES:
            raise RunValidationError(f"{path}.consent_mode has unsupported value {mode!r}")
        is_transporter = tag_key in transporter_tag_keys
        normal_triggers = validate_normal_trigger_bindings(
            item,
            path=path,
            target=target,
            trigger_types=trigger_types,
        )
        trigger_roles = {trigger["role"] for trigger in normal_triggers}
        if role == "event-driven":
            if trigger_roles != {"source-event"}:
                raise RunValidationError(
                    f"{path}.event-driven tags require only source-event triggers"
                )
            if any(trigger["type"] in PAGE_LOAD_TRIGGER_TYPES for trigger in normal_triggers):
                raise RunValidationError(
                    f"{path}.page-load trigger types require baseline-page-load lifecycle"
                )
        expected_baseline_roles = (
            {"cmp-readiness-grant"}
            if mode == "strict-basic"
            else {"initialization-page-load", "cmp-readiness-grant"}
        )
        if role == "baseline-page-load" and not expected_baseline_roles & trigger_roles:
            raise RunValidationError(
                f"{path}.baseline-page-load under {mode} requires a {' or '.join(sorted(expected_baseline_roles))} trigger"
            )

        blocking = semantic_trigger_references(
            item.get("blocking_trigger_keys"),
            f"{path}.blocking_trigger_keys",
        )
        intended_blocks = set(
            tag_trigger_references(target, "blockingTriggerId", f"{path}.bound_tag")
        )
        if set(blocking) != intended_blocks:
            raise RunValidationError(
                f"{path}.blocking_trigger_keys must equal bound blockingTriggerId"
            )
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
        built_in = unique_texts(
            item.get("built_in_consent_checks"),
            f"{path}.built_in_consent_checks",
        )
        # Built-in checks are template behavior, never another configurable firing gate.
        # They can coexist with a strict-basic vendor block. Additional checks below
        # are different: GTM requires all their configured types to be granted.
        # https://support.google.com/tagmanager/answer/10718549
        if tag_type(target, f"{path}.bound_tag") in _GOOGLE_NATIVE_CONSENT_TAG_TYPES and (
            unsupported := set(built_in) - _GOOGLE_NATIVE_CONSENT_TYPES
        ):
            raise RunValidationError(
                f"{path}.built_in_consent_checks contains undocumented Google native "
                f"consent types: {sorted(unsupported)}"
            )
        additional = unique_texts(
            item.get("additional_consent_checks"),
            f"{path}.additional_consent_checks",
        )
        if set(additional) != set(tag_additional_consent_checks(target, f"{path}.bound_tag")):
            raise RunValidationError(
                f"{path}.additional_consent_checks differs from bound tag consentSettings"
            )
        if mode == "strict-basic":
            convention = (consent_enforcements or {}).get(tag_key)
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
                    normal_triggers, blocking, operation_by_key, path
                )
        elif blocking or block_scope or additional:
            raise RunValidationError(
                f"{path}.{mode} must not carry a defeating block or Additional check"
            )
        firing_option = text(item.get("firing_option"), f"{path}.firing_option")
        if firing_option not in FIRING_OPTIONS:
            raise RunValidationError(
                f"{path}.firing_option has unsupported value {firing_option!r}"
            )
        if firing_option != tag_firing_option(target, f"{path}.bound_tag"):
            raise RunValidationError(f"{path}.firing_option differs from the bound tag")
        may_precede_cmp = item.get("may_precede_cmp")
        if mode == "client-policy-ungated" and (
            may_precede_cmp is not False or item.get("pre_cmp_policy") != "not-applicable"
        ):
            raise RunValidationError(
                f"{path}.client-policy-ungated cannot declare CMP-dependent behavior"
            )
        if not isinstance(may_precede_cmp, bool):
            raise RunValidationError(f"{path}.may_precede_cmp must be a boolean")
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
        if not isinstance(item.get("page_view_capable"), bool):
            raise RunValidationError(f"{path}.page_view_capable must be a boolean")
        page_view_destinations = unique_texts(
            item.get("page_view_destinations"),
            f"{path}.page_view_destinations",
        )
        if item["page_view_capable"] != bool(page_view_destinations):
            raise RunValidationError(
                f"{path}.page_view_destinations must be populated exactly when page_view_capable"
            )
        page_view_occurrences = unique_texts(
            item.get("page_view_occurrences"),
            f"{path}.page_view_occurrences",
        )
        if set(page_view_occurrences) - PAGE_VIEW_OCCURRENCES:
            raise RunValidationError(f"{path}.page_view_occurrences contains unsupported values")
        if item["page_view_capable"] != bool(page_view_occurrences):
            raise RunValidationError(
                f"{path}.page_view_occurrences must be populated exactly when page_view_capable"
            )
        ecommerce_route = text(item.get("ecommerce_route"), f"{path}.ecommerce_route")
        if ecommerce_route not in ECOMMERCE_ROUTES:
            raise RunValidationError(
                f"{path}.ecommerce_route has unsupported value {ecommerce_route!r}"
            )
        manual_fields = unique_texts(
            item.get("manual_ecommerce_fields"),
            f"{path}.manual_ecommerce_fields",
        )
        if ecommerce_route != "manual" and manual_fields:
            raise RunValidationError(
                f"{path}.manual_ecommerce_fields must be empty for a native/non-ecommerce route"
            )
        if any(field.startswith("items.0.") for field in manual_fields):
            raise RunValidationError(f"{path} must not flatten items into items.0.* fields")
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
    consent_enforcements = {}
    for index, topology in enumerate(topologies_by_target[target_id]):
        path = f"$.execution_topologies[{index}]"
        validate_topology_consent_binding(
            topology, consent_by_id=consent_by_id, path=path, fail=fail
        )
        local_topologies.append(local_topology(topology, target_id, path, fail))
        enforcements = [
            consent_by_id[key]["web_enforcement"] for key in topology["consent_topology_ids"]
        ]
        if any(item.get("mechanism") in ALTERNATIVE_GATES for item in enforcements) and any(
            item != enforcements[0] for item in enforcements
        ):
            fail("One web tag must have one consistent consent enforcement declaration")
        enforcement = enforcements[0]
        validate_convention(
            topology,
            enforcement,
            {item["object_key"]: item for item in operations},
            fail,
        )
        consent_enforcements[local_topologies[-1]["tag_object_key"]] = enforcement["mechanism"]
    try:
        validated_topologies = validate_execution_topologies(
            local_topologies,
            requirement_ids=set(requirement_ids),
            operations=local_operations,
            baseline_trigger_types={},
            consent_enforcements=consent_enforcements,
            transporter_tag_keys={
                local_key(
                    value,
                    target_id,
                    "$.consent_topologies[].transporter_tag_keys",
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
        target = web_native.effective_target(operation, "$.execution_topologies[].bound_tag")
        tag_type = web_native.tag_type(target, "$.execution_topologies[].bound_tag")
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
