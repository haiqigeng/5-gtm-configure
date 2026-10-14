"""Web page views: shared across preparation and execution."""

from __future__ import annotations

from typing import Any

import gtm_configure.core.validation as validation
import gtm_configure.domain.web_model as web_model
import gtm_configure.domain.web_native as web_native
from gtm_configure.core.validation import (
    RunValidationError,
    array,
    object,
    optional_text,
    text,
    unique_texts,
)
from gtm_configure.domain.localization import local_page_decision
from gtm_configure.domain.web_model import (
    GA4_EVENT_TAG_TYPES,
    GOOGLE_CONFIGURATION_TAG_TYPES,
    NON_EXECUTING_TAG_ACTIONS,
    PAGE_VIEW_OCCURRENCES,
    PAGE_VIEW_OWNERS,
)
from gtm_configure.domain.web_native import (
    configuration_value,
    effective_target,
    send_page_view_value,
    tag_type,
    validate_google_destination,
)


def validate_page_view_decisions(
    raw: Any,
    *,
    requirement_ids: set[str],
    operations: dict[str, dict[str, Any]],
    external_dependencies: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    operation_by_key = {item["object_key"]: item for item in operations.values()}

    def bound_tag(object_key: str, field_path: str) -> tuple[dict[str, Any], dict[str, Any]]:
        operation = operation_by_key.get(object_key)
        if operation is None or operation["object_type"] != "tag":
            raise RunValidationError(f"{field_path} must reference an in-scope tag")
        if operation["action"] in NON_EXECUTING_TAG_ACTIONS:
            raise RunValidationError(f"{field_path} must reference an executing target tag")
        return operation, effective_target(operation, field_path)

    seen: set[tuple[str, str]] = set()
    records: list[dict[str, Any]] = []
    for index, item_raw in enumerate(array(raw, "$.page_view_decisions")):
        path = f"$.page_view_decisions[{index}]"
        item = object(item_raw, path)
        destination = text(item.get("destination"), f"{path}.destination")
        occurrence = text(item.get("occurrence"), f"{path}.occurrence")
        if occurrence not in PAGE_VIEW_OCCURRENCES:
            raise RunValidationError(f"{path}.occurrence has unsupported value {occurrence!r}")
        decision_key = (destination, occurrence)
        if decision_key in seen:
            raise RunValidationError(
                f"duplicate page-view decision for {destination!r} / {occurrence!r}"
            )
        seen.add(decision_key)
        linked = set(
            unique_texts(
                item.get("requirement_ids"),
                f"{path}.requirement_ids",
                allow_empty=False,
            )
        )
        if linked - requirement_ids:
            raise RunValidationError(f"{path}.requirement_ids contains unknown IDs")
        owner = text(item.get("owner"), f"{path}.owner")
        if owner not in PAGE_VIEW_OWNERS:
            raise RunValidationError(f"{path}.owner has unsupported value {owner!r}")
        owner_key = optional_text(item.get("owner_object_key"), f"{path}.owner_object_key")
        google_tag_key = optional_text(
            item.get("google_tag_object_key"),
            f"{path}.google_tag_object_key",
        )
        dependency_ids = set(
            unique_texts(
                item.get("external_dependency_ids"),
                f"{path}.external_dependency_ids",
            )
        )
        if dependency_ids - set(external_dependencies):
            raise RunValidationError(f"{path}.external_dependency_ids contains unknown IDs")
        if any(
            not linked <= set(external_dependencies[dependency_id]["requirement_ids"])
            for dependency_id in dependency_ids
        ):
            raise RunValidationError(
                f"{path}.external_dependency_ids contains a dependency outside the requirements"
            )
        if owner == "google-tag-automatic":
            if occurrence != "initial-page-load":
                raise RunValidationError(
                    f"{path}.google-tag-automatic covers only the initial page load; "
                    "model history-based collection separately"
                )
            if not owner_key or owner_key != google_tag_key:
                raise RunValidationError(
                    f"{path}.google-tag-automatic requires the same owner and Google tag key "
                    "with send_page_view true"
                )
            owner_operation, owner_target = bound_tag(owner_key, f"{path}.owner_object_key")
            if tag_type(owner_target, f"{path}.owner") not in GOOGLE_CONFIGURATION_TAG_TYPES:
                raise RunValidationError(f"{path}.google-tag-automatic owner is not a Google tag")
            if not send_page_view_value(owner_target, f"{path}.owner", operations):
                raise RunValidationError(f"{path}.automatic owner must emit native page_view")
            validate_google_destination(owner_target, destination, f"{path}.owner", operations)
            if not linked <= set(owner_operation["requirement_ids"]):
                raise RunValidationError(f"{path}.owner does not cover its requirement_ids")
        elif owner == "dedicated-ga4-event":
            if not owner_key or not google_tag_key:
                raise RunValidationError(
                    f"{path}.dedicated-ga4-event requires owner and Google tag keys with "
                    "send_page_view false"
                )
            owner_operation, owner_target = bound_tag(owner_key, f"{path}.owner_object_key")
            if tag_type(owner_target, f"{path}.owner") not in GA4_EVENT_TAG_TYPES:
                raise RunValidationError(f"{path}.dedicated-ga4-event owner is not a GA4 Event tag")
            _, event_name = configuration_value(owner_target, {"event_name", "eventName"})
            if event_name != "page_view":
                raise RunValidationError(
                    f"{path}.dedicated-ga4-event owner must send the page_view event"
                )
            validate_google_destination(owner_target, destination, f"{path}.owner", operations)
            if not linked <= set(owner_operation["requirement_ids"]):
                raise RunValidationError(f"{path}.owner does not cover its requirement_ids")
            google_operation, google_target = bound_tag(
                google_tag_key,
                f"{path}.google_tag_object_key",
            )
            if tag_type(google_target, f"{path}.google_tag") not in GOOGLE_CONFIGURATION_TAG_TYPES:
                raise RunValidationError(f"{path}.google_tag_object_key is not a Google tag")
            if send_page_view_value(google_target, f"{path}.google_tag", operations):
                raise RunValidationError(
                    f"{path}.dedicated-ga4-event requires bound Google tag send_page_view false"
                )
            validate_google_destination(
                google_target, destination, f"{path}.google_tag", operations
            )
            if not linked <= set(google_operation["requirement_ids"]):
                raise RunValidationError(f"{path}.Google tag does not cover its requirement_ids")
        elif owner == "internal-tag":
            if not owner_key or google_tag_key is not None:
                raise RunValidationError(
                    f"{path}.internal-tag requires an owner, no Google tag, and null send_page_view"
                )
            owner_operation, _ = bound_tag(owner_key, f"{path}.owner_object_key")
            if not linked <= set(owner_operation["requirement_ids"]):
                raise RunValidationError(f"{path}.owner does not cover its requirement_ids")
        else:
            if owner_key is not None:
                raise RunValidationError(
                    f"{path}.{owner} requires a null owner_object_key and send_page_view null"
                )
            if owner == "external" and not dependency_ids:
                raise RunValidationError(f"{path}.external requires an external dependency")
            if owner == "intentionally-none" and dependency_ids:
                raise RunValidationError(
                    f"{path}.intentionally-none must not claim an external owner"
                )
            if google_tag_key is not None:
                google_operation, google_target = bound_tag(
                    google_tag_key,
                    f"{path}.google_tag_object_key",
                )
                if (
                    tag_type(
                        google_target,
                        f"{path}.google_tag",
                    )
                    not in GOOGLE_CONFIGURATION_TAG_TYPES
                ):
                    raise RunValidationError(f"{path}.google_tag_object_key is not a Google tag")
                if occurrence == "initial-page-load" and send_page_view_value(
                    google_target, f"{path}.google_tag", operations
                ):
                    raise RunValidationError(
                        f"{path}.{owner} requires bound Google tag send_page_view false"
                    )
                validate_google_destination(
                    google_target, destination, f"{path}.google_tag", operations
                )
                if not linked <= set(google_operation["requirement_ids"]):
                    raise RunValidationError(
                        f"{path}.Google tag does not cover its requirement_ids"
                    )
        text(item.get("reason"), f"{path}.reason")
        unique_texts(item.get("evidence"), f"{path}.evidence", allow_empty=False)
        records.append(item)
    return records


def validate_page_view_emitters(*, local_operations, decisions, fail, validated_topologies):
    actual_emitters: dict[tuple[str, str], list[str]] = {}
    trigger_emitters: dict[tuple[str, str], set[str]] = {}
    for topology in validated_topologies.values():
        operation = next(
            item
            for item in local_operations.values()
            if item["object_key"] == topology["tag_object_key"]
        )
        target = web_native.effective_target(operation, "$.tag_policies[].bound_tag")
        tag_type = web_native.tag_type(target, "$.tag_policies[].bound_tag")
        destinations, occurrences = set(), []
        if tag_type in web_model.GOOGLE_CONFIGURATION_TAG_TYPES | web_model.GA4_EVENT_TAG_TYPES:
            try:
                configured = web_native.configured_destinations(
                    target, local_operations, "$.tag_policies[].bound_tag"
                )
            except validation.RunValidationError as exc:
                fail(str(exc))
                return
            ga4 = {value for value in configured if value.startswith("G-")}
            if tag_type in web_model.GOOGLE_CONFIGURATION_TAG_TYPES:
                if not configured or (
                    any(value.startswith("GT-") for value in configured)
                    and not ga4
                    and not any(value.startswith(("AW-", "DC-")) for value in configured)
                ):
                    fail(
                        "Google tag needs inspected destination identities before page-view ownership can be resolved"
                    )
                if web_native.send_page_view_value(
                    target, "$.tag_policies[].bound_tag", local_operations
                ):
                    destinations, occurrences = ga4, ["initial-page-load"]
                if topology.get("page_view_occurrences") or topology.get("custom_page_views"):
                    fail("Google automatic page-view facts come from its native configuration")
            else:
                _, event_name = web_native.configuration_value(target, {"event_name", "eventName"})
                if event_name == "page_view":
                    if not ga4:
                        fail("GA4 page_view tag needs a resolved GA4 destination")
                    destinations, occurrences = ga4, topology.get("page_view_occurrences", [])
                    if not occurrences:
                        fail(
                            "GA4 page_view with an ambiguous occurrence needs page_view_occurrences"
                        )
                elif topology.get("page_view_occurrences"):
                    fail("Page-view occurrence policy requires a native page_view event")
                if topology.get("custom_page_views"):
                    fail("GA4 destinations come from native configuration")
        else:
            custom = topology.get("custom_page_views", {})
            destinations, occurrences = (
                set(custom.get("destinations", [])),
                custom.get("occurrences", []),
            )
            if topology.get("page_view_occurrences"):
                fail("Custom page-view policy owns its destinations and occurrences together")
        if not destinations:
            continue
        for destination in destinations:
            for trigger in topology["trigger_roles"]:
                trigger_emitters.setdefault(
                    (destination, trigger["trigger_object_key"]), set()
                ).add(topology["tag_object_key"])
            try:
                if (
                    tag_type
                    in web_model.GOOGLE_CONFIGURATION_TAG_TYPES | web_model.GA4_EVENT_TAG_TYPES
                ):
                    web_native.validate_google_destination(
                        target,
                        destination,
                        "$.tag_policies[].bound_tag",
                        local_operations,
                    )
            except validation.RunValidationError as exc:
                fail(str(exc))
            for occurrence in occurrences:
                if (
                    tag_type in web_model.GOOGLE_CONFIGURATION_TAG_TYPES
                    and occurrence != "initial-page-load"
                ):
                    continue
                if (
                    occurrence == "virtual-navigation"
                    and web_native.tag_firing_option(target, "$.tag_policies[].bound_tag")
                    == "once-per-page"
                ):
                    fail(
                        f"page-view emitter {topology['tag_object_key']!r} cannot use "
                        "once-per-page for virtual navigation"
                    )
                actual_emitters.setdefault((destination, occurrence), []).append(
                    topology["tag_object_key"]
                )
    for (destination, trigger_key), emitter_keys in trigger_emitters.items():
        if len(emitter_keys) > 1:
            fail(
                f"page-view emitters for {destination!r} share firing trigger {trigger_key!r}; "
                "different occurrence labels do not establish disjoint firing"
            )
    for decision in decisions:
        identity = (decision["destination"], decision["occurrence"])
        emitters = actual_emitters.get(identity, [])
        expected_owner = (
            decision.get("owner_object_key")
            if decision["owner"] in {"google-tag-automatic", "dedicated-ga4-event", "internal-tag"}
            else None
        )
        if expected_owner is None and emitters:
            fail(
                f"page-view decision {identity!r} declares no internal owner but emitters={emitters}"
            )
        elif expected_owner is not None and emitters != [expected_owner]:
            fail(
                f"page-view decision {identity!r} must have exactly its declared emitter; "
                f"emitters={emitters}"
            )

    return actual_emitters


def validate_target_page_views(
    *,
    local_operations,
    dependencies,
    fail,
    page_view_decisions,
    requirement_ids,
    target_id,
    validated_topologies,
):
    local_decisions = []
    for index, decision in enumerate(page_view_decisions):
        if not isinstance(decision, dict) or decision.get("target_id") != target_id:
            continue
        local_decisions.append(
            local_page_decision(decision, target_id, f"$.page_view_decisions[{index}]", fail)
        )
    try:
        decisions = validate_page_view_decisions(
            local_decisions,
            requirement_ids=set(requirement_ids),
            operations=local_operations,
            external_dependencies=dependencies,
        )
    except validation.RunValidationError as exc:
        fail(str(exc))
        return
    actual_emitters = validate_page_view_emitters(
        local_operations=local_operations,
        decisions=decisions,
        fail=fail,
        validated_topologies=validated_topologies,
    )
    decision_occurrences = {(item["destination"], item["occurrence"]) for item in decisions}
    missing = set(actual_emitters) - decision_occurrences
    if missing:
        fail(
            f"web target {target_id!r} page-view decisions must cover native emitted occurrences; missing={sorted(missing)}"
        )
