"""Web page views: shared across preparation and execution."""

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
    GA4_EVENT_TAG_TYPES,
    GOOGLE_CONFIGURATION_TAG_TYPES,
    NON_EXECUTING_TAG_ACTIONS,
    PAGE_VIEW_OCCURRENCES,
    PAGE_VIEW_OWNERS,
)
from gtm_configure.domain.web_native import (
    _configuration_value,
    _effective_target,
    _send_page_view_value,
    _tag_type,
    _validate_google_destination,
)


def _validate_page_view_decisions(
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
        return operation, _effective_target(operation, field_path)

    seen: set[tuple[str, str]] = set()
    records: list[dict[str, Any]] = []
    for index, item_raw in enumerate(_array(raw, "$.page_view_decisions")):
        path = f"$.page_view_decisions[{index}]"
        item = _object(item_raw, path)
        _exact_keys(
            item,
            path,
            required={
                "destination",
                "occurrence",
                "requirement_ids",
                "owner",
                "owner_object_key",
                "google_tag_object_key",
                "send_page_view",
                "external_dependency_ids",
                "reason",
                "evidence",
            },
        )
        destination = _text(item.get("destination"), f"{path}.destination")
        occurrence = _text(item.get("occurrence"), f"{path}.occurrence")
        if occurrence not in PAGE_VIEW_OCCURRENCES:
            raise RunValidationError(f"{path}.occurrence has unsupported value {occurrence!r}")
        decision_key = (destination, occurrence)
        if decision_key in seen:
            raise RunValidationError(
                f"duplicate page-view decision for {destination!r} / {occurrence!r}"
            )
        seen.add(decision_key)
        linked = set(
            _unique_texts(
                item.get("requirement_ids"),
                f"{path}.requirement_ids",
                allow_empty=False,
            )
        )
        if linked - requirement_ids:
            raise RunValidationError(f"{path}.requirement_ids contains unknown IDs")
        owner = _text(item.get("owner"), f"{path}.owner")
        if owner not in PAGE_VIEW_OWNERS:
            raise RunValidationError(f"{path}.owner has unsupported value {owner!r}")
        owner_key = _optional_text(item.get("owner_object_key"), f"{path}.owner_object_key")
        google_tag_key = _optional_text(
            item.get("google_tag_object_key"),
            f"{path}.google_tag_object_key",
        )
        dependency_ids = set(
            _unique_texts(
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
        send_page_view = item.get("send_page_view")
        if send_page_view is not None and not isinstance(send_page_view, bool):
            raise RunValidationError(f"{path}.send_page_view must be boolean or null")
        if owner == "google-tag-automatic":
            if occurrence != "initial-page-load":
                raise RunValidationError(
                    f"{path}.google-tag-automatic covers only the initial page load; "
                    "model history-based collection separately"
                )
            if not owner_key or owner_key != google_tag_key or send_page_view is not True:
                raise RunValidationError(
                    f"{path}.google-tag-automatic requires the same owner and Google tag key "
                    "with send_page_view true"
                )
            owner_operation, owner_target = bound_tag(owner_key, f"{path}.owner_object_key")
            if _tag_type(owner_target, f"{path}.owner") not in GOOGLE_CONFIGURATION_TAG_TYPES:
                raise RunValidationError(f"{path}.google-tag-automatic owner is not a Google tag")
            if not _send_page_view_value(owner_target, f"{path}.owner", operations):
                raise RunValidationError(f"{path}.send_page_view differs from the bound Google tag")
            _validate_google_destination(owner_target, destination, f"{path}.owner", operations)
            if not linked <= set(owner_operation["requirement_ids"]):
                raise RunValidationError(f"{path}.owner does not cover its requirement_ids")
        elif owner == "dedicated-ga4-event":
            if not owner_key or not google_tag_key or send_page_view is not False:
                raise RunValidationError(
                    f"{path}.dedicated-ga4-event requires owner and Google tag keys with "
                    "send_page_view false"
                )
            owner_operation, owner_target = bound_tag(owner_key, f"{path}.owner_object_key")
            if _tag_type(owner_target, f"{path}.owner") not in GA4_EVENT_TAG_TYPES:
                raise RunValidationError(f"{path}.dedicated-ga4-event owner is not a GA4 Event tag")
            _, event_name = _configuration_value(owner_target, {"event_name", "eventName"})
            if event_name != "page_view":
                raise RunValidationError(
                    f"{path}.dedicated-ga4-event owner must send the page_view event"
                )
            _validate_google_destination(owner_target, destination, f"{path}.owner", operations)
            if not linked <= set(owner_operation["requirement_ids"]):
                raise RunValidationError(f"{path}.owner does not cover its requirement_ids")
            google_operation, google_target = bound_tag(
                google_tag_key,
                f"{path}.google_tag_object_key",
            )
            if _tag_type(google_target, f"{path}.google_tag") not in GOOGLE_CONFIGURATION_TAG_TYPES:
                raise RunValidationError(f"{path}.google_tag_object_key is not a Google tag")
            if _send_page_view_value(google_target, f"{path}.google_tag", operations):
                raise RunValidationError(
                    f"{path}.dedicated-ga4-event requires bound Google tag send_page_view false"
                )
            _validate_google_destination(
                google_target, destination, f"{path}.google_tag", operations
            )
            if not linked <= set(google_operation["requirement_ids"]):
                raise RunValidationError(f"{path}.Google tag does not cover its requirement_ids")
        elif owner == "internal-tag":
            if not owner_key or google_tag_key is not None or send_page_view is not None:
                raise RunValidationError(
                    f"{path}.internal-tag requires an owner, no Google tag, and null send_page_view"
                )
            owner_operation, _ = bound_tag(owner_key, f"{path}.owner_object_key")
            if not linked <= set(owner_operation["requirement_ids"]):
                raise RunValidationError(f"{path}.owner does not cover its requirement_ids")
        else:
            if owner_key is not None or send_page_view is not None:
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
                    _tag_type(
                        google_target,
                        f"{path}.google_tag",
                    )
                    not in GOOGLE_CONFIGURATION_TAG_TYPES
                ):
                    raise RunValidationError(f"{path}.google_tag_object_key is not a Google tag")
                if occurrence == "initial-page-load" and _send_page_view_value(
                    google_target, f"{path}.google_tag", operations
                ):
                    raise RunValidationError(
                        f"{path}.{owner} requires bound Google tag send_page_view false"
                    )
                _validate_google_destination(
                    google_target, destination, f"{path}.google_tag", operations
                )
                if not linked <= set(google_operation["requirement_ids"]):
                    raise RunValidationError(
                        f"{path}.Google tag does not cover its requirement_ids"
                    )
        _text(item.get("reason"), f"{path}.reason")
        _unique_texts(item.get("evidence"), f"{path}.evidence", allow_empty=False)
        records.append(item)
    return records
