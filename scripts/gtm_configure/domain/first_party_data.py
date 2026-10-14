"""Web identity: shared across preparation and execution."""

from __future__ import annotations

from typing import Any

import gtm_configure.core.validation as validation
import gtm_configure.domain.web_model as web_model
import gtm_configure.domain.web_native as web_native
from gtm_configure.core.public_identifiers import locate
from gtm_configure.core.validation import (
    RunValidationError,
    array,
    object,
    optional_text,
    text,
    unique_texts,
)
from gtm_configure.domain.events import approved_event_name, trigger_accepts_event
from gtm_configure.domain.localization import local_first_party_route
from gtm_configure.domain.native import (
    USER_DATA_VARIABLE_TYPES,
    FieldResolutionError,
    field_key,
    referenced_variable_closure,
    sensitive_fields,
)
from gtm_configure.domain.web_model import (
    CUSTOM_CODE_TAG_TYPES,
    FIRST_PARTY_FEATURES,
    FIRST_PARTY_PRODUCTS,
    GA4_EVENT_TAG_TYPES,
    GOOGLE_ADS_CONVERSION_TAG_TYPES,
    GOOGLE_CONFIGURATION_TAG_TYPES,
    NON_EXECUTING_TAG_ACTIONS,
)
from gtm_configure.domain.web_native import (
    configuration_value,
    effective_target,
    field_value,
    normalized_token,
    resolved_collection_fields,
    resolved_fields,
    tag_type,
)


def validate_first_party_feature_contract(
    *,
    path: str,
    feature: str,
    destination_field: str,
    timing: str,
    hashing_owner: str,
    field_names: set[str],
    consumer_targets: list[dict[str, Any]],
    dependency_ids: set[str],
    consent_types: set[str],
) -> None:
    product_types = {tag_type(target, f"{path}.consumer") for target in consumer_targets}
    if feature == "analytics-user-id":
        if (
            hashing_owner != "not-applicable"
            or timing not in {"tag-wide", "same-event"}
            or destination_field != "user_id"
            or field_names != {"user_id"}
        ):
            raise RunValidationError(
                f"{path}.analytics-user-id requires user_id, tag-wide or same-event timing, "
                "one user_id field, and no hashing"
            )
        if product_types & (
            GOOGLE_CONFIGURATION_TAG_TYPES | GA4_EVENT_TAG_TYPES | GOOGLE_ADS_CONVERSION_TAG_TYPES
        ):
            raise RunValidationError(
                f"{path}.analytics-user-id is reserved for non-Google analytics consumers"
            )
        return
    if feature == "ga4-user-id":
        if (
            hashing_owner != "not-applicable"
            or timing != "tag-wide"
            or destination_field != "user_id"
        ):
            raise RunValidationError(
                f"{path}.ga4-user-id requires destination user_id, tag-wide timing, and no hashing"
            )
        if field_names != {"user_id"}:
            raise RunValidationError(f"{path}.ga4-user-id requires only the user_id field")
        if not product_types <= GOOGLE_CONFIGURATION_TAG_TYPES:
            raise RunValidationError(f"{path}.ga4-user-id requires a Google configuration tag")
        return

    if hashing_owner == "not-applicable":
        raise RunValidationError(f"{path}.{feature} requires an explicit hashing owner")
    if feature == "ga4-user-provided-data":
        if destination_field != "user_data" or timing != "same-event":
            raise RunValidationError(f"{path}.ga4-user-provided-data requires same-event user_data")
        if not product_types <= GA4_EVENT_TAG_TYPES:
            raise RunValidationError(f"{path}.ga4-user-provided-data requires GA4 Event tags")
    elif feature == "google-ads-enhanced-conversions":
        if destination_field != "user_data" or timing != "same-event":
            raise RunValidationError(
                f"{path}.google-ads-enhanced-conversions requires same-event user_data"
            )
        if not product_types <= GOOGLE_ADS_CONVERSION_TAG_TYPES:
            raise RunValidationError(
                f"{path}.google-ads-enhanced-conversions requires native Ads conversion event tags; "
                "a Google tag user_data field is tag-wide and requires the explicitly authorized "
                "google-ads-tag-wide-user-data route"
            )
    elif feature == "google-ads-tag-wide-user-data":
        if destination_field != "user_data" or timing != "tag-wide":
            raise RunValidationError(
                f"{path}.google-ads-tag-wide-user-data requires tag-wide user_data"
            )
        if not product_types <= {"googtag"}:
            raise RunValidationError(
                f"{path}.google-ads-tag-wide-user-data requires a current Google tag"
            )
    elif feature == "google-ads-user-provided-data-event":
        if destination_field != "user_data" or timing != "prior-page":
            raise RunValidationError(
                f"{path}.google-ads-user-provided-data-event requires prior-page user_data"
            )
        if product_types != {"googleadsuserprovideddataevent"}:
            raise RunValidationError(
                f"{path}.google-ads-user-provided-data-event requires the native "
                "Google Ads User-Provided Data Event tag"
            )
    elif feature == "google-ads-server-user-data-transport":
        if destination_field != "user_data" or timing not in {"same-event", "tag-wide"}:
            raise RunValidationError(
                f"{path}.{feature} requires same-event or explicitly authorized tag-wide user_data"
            )
        expected_types = GA4_EVENT_TAG_TYPES if timing == "same-event" else {"googtag"}
        if not product_types <= expected_types:
            owner = "GA4 Event sender" if timing == "same-event" else "Google tag sender"
            raise RunValidationError(f"{path}.{feature} requires the documented {owner}")
    elif feature == "google-ads-server-user-provided-data-event":
        if destination_field != "user_data" or timing != "prior-page":
            raise RunValidationError(
                f"{path}.{feature} requires prior-page user_data on the event where it is available"
            )
        if not product_types <= ({"googtag"} | GA4_EVENT_TAG_TYPES):
            raise RunValidationError(
                f"{path}.{feature} requires a Google tag or GA4 Event user_data sender"
            )

    if feature.startswith("google-ads-") and feature not in {
        "google-ads-enhanced-conversions",
        "google-ads-tag-wide-user-data",
        "google-ads-server-user-data-transport",
        "google-ads-server-user-provided-data-event",
    }:
        if product_types & (GOOGLE_CONFIGURATION_TAG_TYPES | GA4_EVENT_TAG_TYPES):
            raise RunValidationError(
                f"{path}.{feature} must not bind a GA4 or generic Google configuration tag"
            )
    externally_administered = {
        "ga4-user-provided-data",
        "google-ads-enhanced-conversions",
        "google-ads-tag-wide-user-data",
        "google-ads-user-provided-data-event",
        "google-ads-server-user-data-transport",
        "google-ads-server-user-provided-data-event",
    }
    if feature in externally_administered and not dependency_ids:
        raise RunValidationError(f"{path}.{feature} requires an external administration dependency")
    if feature in externally_administered and "ad_user_data" not in consent_types:
        raise RunValidationError(f"{path}.{feature} requires ad_user_data consent")


def first_party_binding_value(
    route: dict[str, Any],
    target: dict[str, Any],
    object_key: str,
    path: str,
    operations: dict[str, dict[str, Any]] | None = None,
) -> tuple[bool, Any]:
    """Resolve an inspected event override without guessing a native Ads parameter name."""
    if route.get("feature") == "ga4-user-id":
        fields = resolved_collection_fields(target, operations, path, namespace="configuration")
        name = route["destination_field"]
        return name in fields, fields.get(name)
    native_matching = route.get("feature") == "vendor-advanced-matching" and any(
        "user_data_path" in binding for binding in route.get("consumer_bindings", [])
    )
    if route.get("feature") != "google-ads-enhanced-conversions" and not native_matching:
        if route.get("feature") == "ga4-user-provided-data":
            return configuration_value(target, {route["destination_field"]})
        return field_value(
            resolved_fields(
                target,
                operations,
                path,
            ),
            {route["destination_field"]},
        )
    bindings = array(route.get("consumer_bindings"), f"{path}.consumer_bindings")
    matches = [
        item for item in bindings if isinstance(item, dict) and item.get("object_key") == object_key
    ]
    if len(matches) != 1:
        raise RunValidationError(f"{path} needs exactly one native field binding per consumer")
    binding = matches[0]
    text(binding.get("field_review"), f"{path}.consumer_binding.field_review")
    if native_matching:
        cell_path = binding.get("user_data_path")
        if (
            not isinstance(cell_path, list)
            or len(cell_path) != 7
            or cell_path[:3] != ["parameter", "advancedMatchingList", "list"]
            or type(cell_path[3]) is not int
            or cell_path[3] < 0
            or cell_path[4:] != ["map", "value", "value"]
        ):
            raise RunValidationError(f"{path} must bind an advancedMatchingList value cell")
        try:
            matching_name, _ = locate(target, cell_path[:4] + ["map", "name", "value"])
        except (KeyError, TypeError, IndexError) as exc:
            raise RunValidationError(f"{path} matching row has no unique name") from exc
        if route.get("destination_field") != matching_name or [
            field.get("name") for field in route.get("fields", [])
        ] != [matching_name]:
            raise RunValidationError(
                f"{path} scalar matching binding must prove exactly its one approved field"
            )
        rows = resolved_fields(target, operations, path).get("advancedmatchinglist", [])
        if (
            not isinstance(rows, list)
            or sum(isinstance(row, dict) and row.get("name") == matching_name for row in rows) != 1
        ):
            raise RunValidationError(
                f"{path} matching field must have exactly one native table row"
            )
        if binding.get("activation_paths") != [["parameter", "advancedMatching", "value"]]:
            raise RunValidationError(f"{path} must bind the native advancedMatching control")

    def native_value(native_path: Any) -> Any:
        if (
            not isinstance(native_path, list)
            or len(native_path) < 3
            or native_path[0] != "parameter"
            or native_path[-1] != "value"
            or any(
                not (isinstance(part, str) and part or type(part) is int and part >= 0)
                for part in native_path
            )
        ):
            raise RunValidationError(
                f"{path}.user_data_path/activation_paths must identify an inspected native parameter value"
            )
        try:
            value, _ = locate(target, native_path)
        except (KeyError, TypeError, IndexError) as exc:
            raise RunValidationError(
                f"{path}.native field path does not resolve uniquely in the native tag"
            ) from exc
        return value

    for activation_path in array(binding.get("activation_paths"), f"{path}.activation_paths"):
        activation = native_value(activation_path)
        if activation is not True and activation != "true":
            raise RunValidationError(f"{path}.required native user-data control is not enabled")
    return True, native_value(binding.get("user_data_path"))


def _validate_first_party_consumer_bindings(
    raw: Any,
    *,
    path: str,
    feature: str,
    consumers: set[str],
    consumer_targets: dict[str, dict[str, Any]],
) -> None:
    records: set[str] = set()
    for index, binding_raw in enumerate(array(raw, f"{path}.consumer_bindings")):
        binding_path = f"{path}.consumer_bindings[{index}]"
        binding = object(binding_raw, binding_path)
        object_key = text(binding.get("object_key"), f"{binding_path}.object_key")
        if object_key not in consumers or object_key in records:
            raise RunValidationError(
                f"{binding_path}.object_key is unknown or duplicated for this route"
            )
        records.add(object_key)
        product = normalized_token(text(binding.get("product"), f"{binding_path}.product"))
        expected_product = FIRST_PARTY_PRODUCTS.get(feature)
        if expected_product is not None and product != normalized_token(expected_product):
            raise RunValidationError(
                f"{binding_path}.product must identify {expected_product!r} for {feature}"
            )
        implementation = text(binding.get("implementation"), f"{binding_path}.implementation")
        if implementation not in {"native", "installed-template"}:
            raise RunValidationError(f"{binding_path}.implementation is unsupported")
        if feature == "google-ads-enhanced-conversions" and implementation != "native":
            raise RunValidationError(f"{binding_path}.event override requires a native Ads tag")
        actual_type = tag_type(consumer_targets[object_key], f"{binding_path}.consumer")
        declared_type = normalized_token(text(binding.get("tag_type"), f"{binding_path}.tag_type"))
        if declared_type != actual_type:
            raise RunValidationError(
                f"{binding_path}.tag_type differs from the bound saved tag type"
            )
        if actual_type in CUSTOM_CODE_TAG_TYPES:
            raise RunValidationError(
                f"{binding_path} cannot identify Custom HTML/Image as a product-native consumer"
            )
        template_identity = optional_text(
            binding.get("template_identity"), f"{binding_path}.template_identity"
        )
        if implementation == "native" and template_identity is not None:
            raise RunValidationError(f"{binding_path}.native requires a null template_identity")
        if implementation == "installed-template":
            if template_identity is None:
                raise RunValidationError(
                    f"{binding_path}.installed-template requires template_identity"
                )
            if normalized_token(template_identity) != actual_type:
                raise RunValidationError(
                    f"{binding_path}.template_identity differs from the bound saved tag type"
                )
        unique_texts(
            binding.get("evidence"),
            f"{binding_path}.evidence",
            allow_empty=False,
        )
    if records != consumers:
        missing = sorted(consumers - records)
        raise RunValidationError(
            f"{path}.consumer_bindings must identify every consumer exactly; missing={missing}"
        )


def validate_first_party_data_routes(
    raw: Any,
    *,
    requirement_ids: set[str],
    operations: dict[str, dict[str, Any]],
    external_dependencies: dict[str, dict[str, Any]],
    payload_mappings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    operation_by_key = {item["object_key"]: item for item in operations.values()}
    mapping_by_identity = {}
    for mapping in payload_mappings:
        if mapping["status"] == "mapped":
            mapping_by_identity.setdefault(
                (mapping["requirement_id"], mapping["destination_field"]), []
            ).append(mapping)
    identities: set[tuple[str, str, str]] = set()
    records: list[dict[str, Any]] = []
    for index, item_raw in enumerate(array(raw, "$.first_party_data_routes")):
        path = f"$.first_party_data_routes[{index}]"
        item = object(item_raw, path)
        requirement_id = text(item.get("requirement_id"), f"{path}.requirement_id")
        if requirement_id not in requirement_ids:
            raise RunValidationError(f"{path}.requirement_id is unknown")
        feature = text(item.get("feature"), f"{path}.feature")
        if feature not in FIRST_PARTY_FEATURES:
            raise RunValidationError(f"{path}.feature has unsupported value {feature!r}")
        destination_field = text(
            item.get("destination_field"),
            f"{path}.destination_field",
        )
        matching_fields = mapping_by_identity.get((requirement_id, destination_field), [])
        if len(matching_fields) != 1:
            raise RunValidationError(
                f"{path} must bind to a mapped payload field {requirement_id}::{destination_field}"
            )
        if feature == "ga4-user-id" and matching_fields[0]["field_scope"] != "configuration":
            raise RunValidationError(f"{path}.ga4-user-id binds the configuration namespace")
        identity = (
            requirement_id,
            feature,
            destination_field if feature == "vendor-advanced-matching" else "",
        )
        if identity in identities:
            raise RunValidationError(f"duplicate first-party-data route {identity!r}")
        identities.add(identity)
        consumers = set(
            unique_texts(
                item.get("consumer_object_keys"),
                f"{path}.consumer_object_keys",
                allow_empty=False,
            )
        )
        consumer_targets: dict[str, dict[str, Any]] = {}
        for object_key in consumers:
            operation = operation_by_key.get(object_key)
            if operation is None or operation["object_type"] != "tag":
                raise RunValidationError(
                    f"{path}.consumer_object_keys contains a non-tag or unknown object"
                )
            if operation["action"] in NON_EXECUTING_TAG_ACTIONS:
                raise RunValidationError(
                    f"{path}.consumer_object_keys contains a non-executing tag"
                )
            if requirement_id not in operation["requirement_ids"]:
                raise RunValidationError(
                    f"{path}.consumer_object_keys contains a tag outside the requirement"
                )
            target = effective_target(operation, f"{path}.consumer_object_keys")
            present, configured_value = first_party_binding_value(
                item, target, object_key, path, operations
            )
            if not present:
                raise RunValidationError(
                    f"{path}.consumer {object_key!r} does not configure {destination_field!r}"
                )
            expected_binding = matching_fields[0].get("gtm_resolution")
            if expected_binding is not None and validation.canonical_sha256(
                configured_value
            ) != validation.canonical_sha256(expected_binding):
                raise RunValidationError(
                    f"{path}.consumer {object_key!r} {destination_field!r} binding differs "
                    "from the approved field binding"
                )
            if feature == "vendor-advanced-matching" and any(
                "user_data_path" in binding for binding in item.get("consumer_bindings", [])
            ):
                mapping = matching_fields[0]
                if item.get("timing") != "same-event":
                    raise RunValidationError(f"{path} native matching requires same-event timing")
                if item["fields"][0].get("source") != mapping.get("source"):
                    raise RunValidationError(
                        f"{path} matching source differs from the approved field"
                    )
            consumer_targets[object_key] = target
        if "consumer_bindings" in item:
            _validate_first_party_consumer_bindings(
                item["consumer_bindings"],
                path=path,
                feature=feature,
                consumers=consumers,
                consumer_targets=consumer_targets,
            )
        source_priority = text(item.get("source_priority"), f"{path}.source_priority")
        if source_priority not in {
            "data-layer",
            "controlled-javascript",
            "dom",
            "automatic",
        }:
            raise RunValidationError(f"{path}.source_priority is unsupported")
        timing = text(item.get("timing"), f"{path}.timing")
        if timing not in {"tag-wide", "same-event", "prior-page"}:
            raise RunValidationError(f"{path}.timing is unsupported")
        hashing_owner = text(item.get("hashing_owner"), f"{path}.hashing_owner")
        if hashing_owner not in {"not-applicable", "native-raw", "prehashed-sha256"}:
            raise RunValidationError(f"{path}.hashing_owner is unsupported")
        fields = array(item.get("fields"), f"{path}.fields")
        if not fields:
            raise RunValidationError(f"{path}.fields must not be empty")
        field_names: set[str] = set()
        for field_index, field_raw in enumerate(fields):
            field_path = f"{path}.fields[{field_index}]"
            field = object(field_raw, field_path)
            name = text(field.get("name"), f"{field_path}.name")
            if name in field_names:
                raise RunValidationError(f"{path}.fields contains duplicate field {name!r}")
            field_names.add(name)
            text(field.get("source"), f"{field_path}.source")
            unique_texts(field.get("normalization"), f"{field_path}.normalization")
            if field.get("empty_behavior") != "omit":
                raise RunValidationError(f"{field_path}.empty_behavior must be 'omit'")
        if feature == "ga4-user-id" and fields[0]["source"] != matching_fields[0]["source"]:
            raise RunValidationError(
                f"{path}.identity source differs from its approved configuration mapping"
            )
        consent_types = set(unique_texts(item.get("consent_types"), f"{path}.consent_types"))
        dependency_ids = set(
            unique_texts(
                item.get("external_dependency_ids"),
                f"{path}.external_dependency_ids",
            )
        )
        if dependency_ids - set(external_dependencies):
            raise RunValidationError(f"{path}.external_dependency_ids contains unknown IDs")
        if any(
            requirement_id not in external_dependencies[dependency_id]["requirement_ids"]
            for dependency_id in dependency_ids
        ):
            raise RunValidationError(
                f"{path}.external_dependency_ids contains a dependency outside the requirement"
            )
        unique_texts(item.get("evidence"), f"{path}.evidence", allow_empty=False)
        validate_first_party_feature_contract(
            path=path,
            feature=feature,
            destination_field=destination_field,
            timing=timing,
            hashing_owner=hashing_owner,
            field_names=field_names,
            consumer_targets=list(consumer_targets.values()),
            dependency_ids=dependency_ids,
            consent_types=consent_types,
        )
        records.append(item)
    return records


def contains_configuration_key(value: Any, keys: set[str]) -> bool:
    if isinstance(value, dict):
        row_key = value.get("key")
        if isinstance(row_key, str) and web_native.normalized_token(row_key) in keys:
            return True
        return any(
            web_native.normalized_token(str(key)) in keys or contains_configuration_key(child, keys)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(contains_configuration_key(child, keys) for child in value)
    return False


def validate_server_identity_consumers(*, fail, first_party_data_routes, operations, target_types):
    authorized_server_consumers = {
        key
        for route in first_party_data_routes
        if isinstance(route, dict)
        for key in route.get("server_consumer_object_keys", [])
        if isinstance(key, str)
    }
    for operation in operations:
        if (
            not isinstance(operation, dict)
            or target_types.get(operation.get("target_id")) != "server"
            or (operation.get("resource_family") or operation.get("object_type")) != "tag"
            or operation.get("action") in web_model.NON_EXECUTING_TAG_ACTIONS
        ):
            continue
        target = operation.get("intended") or operation.get("pre_change") or {}
        if contains_configuration_key(target, {"userdata", "userid", "userprovideddata"}):
            if operation.get("object_key") not in authorized_server_consumers:
                fail(
                    f"server tag {operation.get('object_key')!r} configures first-party user "
                    "data without an authorized first-party-data route"
                )


def validate_transport_routes(
    *,
    dependencies,
    fail,
    first_party_data_routes,
    operations,
    pipelines,
    target_types,
    web_target_ids,
):
    for index, route in enumerate(first_party_data_routes):
        if not isinstance(route, dict):
            fail(f"$.first_party_data_routes[{index}] must be an object")
            continue
        consumers = route.get("consumer_object_keys")
        if not isinstance(consumers, list) or not consumers:
            fail(f"$.first_party_data_routes[{index}].consumer_object_keys must not be empty")
            continue
        target_ids = {value.split("::", 1)[0] for value in consumers if isinstance(value, str)}
        if len(target_ids) != 1 or not target_ids <= web_target_ids:
            fail(f"$.first_party_data_routes[{index}] must stay inside one web target")
        server_feature = route.get("feature")
        if server_feature in {
            "google-ads-server-user-data-transport",
            "google-ads-server-user-provided-data-event",
        }:
            receiver_keys = route.get("server_consumer_object_keys")
            if set(target_types.values()) == {"web"}:
                dependency_id = route.get("external_receiver_dependency_id")
                dependency = dependencies.get(dependency_id, {})
                if (
                    server_feature != "google-ads-server-user-data-transport"
                    or route.get("timing") != "same-event"
                    or receiver_keys != []
                    or dependency_id not in route.get("external_dependency_ids", [])
                    or route.get("requirement_id") not in dependency.get("requirement_ids", [])
                ):
                    fail(
                        f"$.first_party_data_routes[{index}] sender-only user_data needs same-event scope and its explicit external receiver dependency"
                    )
                continue
            if route.get("external_receiver_dependency_id") is not None:
                fail(
                    f"$.first_party_data_routes[{index}] full pipeline requires in-scope receiver proof"
                )
            if (
                not isinstance(receiver_keys, list)
                or not receiver_keys
                or any(not isinstance(key, str) for key in receiver_keys)
            ):
                fail(f"$.first_party_data_routes[{index}] needs explicit server consumers")
                continue
            if len(set(receiver_keys)) != len(receiver_keys):
                fail(f"$.first_party_data_routes[{index}] has duplicate server consumers")
            operation_by_key = {item.get("object_key"): item for item in operations}
            expected_receiver_types = (
                {"googleadsuserprovideddataevent"}
                if server_feature == "google-ads-server-user-provided-data-event"
                else {"awct", "googleadsconversion", "googleadsconversiontracking"}
            )
            for receiver_key in receiver_keys:
                receiver = operation_by_key.get(receiver_key)
                receiver_type = web_native.normalized_token(
                    str((receiver or {}).get("intended", {}).get("type", ""))
                )
                if (
                    receiver is None
                    or target_types.get(receiver.get("target_id")) != "server"
                    or receiver.get("resource_family") != "tag"
                    or receiver_type not in expected_receiver_types
                ):
                    expected_owner = (
                        "Google Ads User-provided Data Event"
                        if server_feature == "google-ads-server-user-provided-data-event"
                        else "Google Ads Conversion Tracking"
                    )
                    fail(
                        f"$.first_party_data_routes[{index}] server consumer must be the "
                        f"{expected_owner} tag that consumes transported user_data"
                    )
            requirement_id = route.get("requirement_id")
            proved_receivers: set[str] = set()
            for pipeline in pipelines:
                if not target_ids <= set(pipeline.get("sending_target_ids", [])):
                    continue
                event_receivers = {
                    key
                    for flow in pipeline.get("event_flows", [])
                    if flow.get("requirement_id") == requirement_id
                    for key in flow.get("server_consumer_keys", [])
                }
                for field in pipeline.get("field_flows", []):
                    if (
                        field.get("status") == "proved"
                        and requirement_id in field.get("requirement_ids", [])
                        and field.get("wire") == {"path": "user_data", "shape": "object"}
                        and field.get("event_data") == {"path": "user_data", "shape": "object"}
                        and field.get("receiver_owner") in event_receivers
                    ):
                        proved_receivers.add(field["receiver_owner"])
            if proved_receivers != set(receiver_keys):
                fail(
                    f"$.first_party_data_routes[{index}] server user_data transport requires "
                    "proved pipeline fields for exactly its authorized receiving consumers"
                )


def validate_target_routes(
    *,
    local_operations,
    dependencies,
    fail,
    first_party_data_routes,
    mappings,
    requirement_by_id,
    requirement_ids,
    target_id,
    validated_topologies,
):
    local_routes = []
    for index, route in enumerate(first_party_data_routes):
        if not isinstance(route, dict):
            continue
        consumers = route.get("consumer_object_keys", [])
        if not isinstance(consumers, list) or not consumers:
            fail(f"$.first_party_data_routes[{index}].consumer_object_keys must not be empty")
            continue
        target_ids = {value.split("::", 1)[0] for value in consumers if isinstance(value, str)}
        if target_id in target_ids:
            local_routes.append(
                local_first_party_route(
                    route, target_id, f"$.first_party_data_routes[{index}]", fail
                )
            )
    try:
        validated_routes = validate_first_party_data_routes(
            local_routes,
            requirement_ids=set(requirement_ids),
            operations=local_operations,
            external_dependencies=dependencies,
            payload_mappings=mappings,
        )
    except validation.RunValidationError as exc:
        fail(str(exc))
        return

    for route in validated_routes:
        if route["feature"] == "google-ads-server-user-provided-data-event":
            requirement = requirement_by_id.get(route["requirement_id"], {})
            source_event = approved_event_name(requirement)
            operations_by_key = {item["object_key"]: item for item in local_operations.values()}
            for consumer_key in route["consumer_object_keys"]:
                topology = validated_topologies.get(consumer_key, {})
                triggers = topology.get("normal_triggers", [])
                if (
                    not source_event
                    or not triggers
                    or not all(
                        trigger_accepts_event(
                            web_native.effective_target(
                                operations_by_key.get(trigger["trigger_object_key"], {}),
                                "$.first_party_data_routes[].capture_trigger",
                            ),
                            source_event,
                        )
                        for trigger in triggers
                    )
                ):
                    fail(
                        f"first-party route {route['requirement_id']!r} prior-page user_data "
                        "must resolve on its approved source event, not only at initialization; "
                        "use the documented event-scoped sender when data becomes available later"
                    )
        if route["feature"] not in {
            "google-ads-user-provided-data-event",
            "google-ads-enhanced-conversions",
        }:
            continue
        if route["feature"] == "google-ads-user-provided-data-event":
            requirement = requirement_by_id.get(route["requirement_id"], {})
            if requirement.get("source_event") != "gtm.formSubmit":
                fail(
                    f"first-party route {route['requirement_id']!r} must bind the "
                    "gtm.formSubmit source event for prior-page browser capture"
                )
            for consumer_key in route["consumer_object_keys"]:
                topology = validated_topologies.get(consumer_key)
                if topology is None or {
                    trigger["type"] for trigger in topology["normal_triggers"]
                } != {"form-submission"}:
                    fail(
                        f"first-party route {route['requirement_id']!r} must bind the "
                        "native Form Submission trigger for prior-page browser capture"
                    )
        for consumer_key in route["consumer_object_keys"]:
            consumer = next(
                item for item in local_operations.values() if item["object_key"] == consumer_key
            )
            _, binding_value = first_party_binding_value(
                route,
                web_native.effective_target(consumer, "$.first_party_data_routes[].consumer"),
                consumer_key,
                "$.first_party_data_routes[]",
                local_operations,
            )
            if not (
                isinstance(binding_value, str)
                and binding_value.startswith("{{")
                and binding_value.endswith("}}")
            ):
                fail(
                    f"first-party route {route['requirement_id']!r} must reference a "
                    "User-Provided Data variable"
                )
                continue
            variable_name = binding_value[2:-2].strip()
            variable = next(
                (
                    item
                    for item in local_operations.values()
                    if item["object_type"] == "variable" and item["name"] == variable_name
                ),
                None,
            )
            variable_type = (
                web_native.normalized_token(
                    str(
                        web_native.effective_target(
                            variable, "$.first_party_data_routes[].variable"
                        ).get("type", "")
                    )
                )
                if variable is not None
                else ""
            )
            if variable_type not in USER_DATA_VARIABLE_TYPES:
                fail(
                    f"first-party route {route['requirement_id']!r} must bind a native "
                    "User-Provided Data variable"
                )
    return local_routes, validated_routes


def validate_consumer_scope(*, local_operations, fail, validated_routes):
    variable_targets = {
        operation["name"]: web_native.effective_target(operation, "$.variable")
        for operation in local_operations.values()
        if operation["object_type"] == "variable"
        and operation["action"] not in web_model.NON_EXECUTING_TAG_ACTIONS
    }
    authorized_variable_names: set[str] = set()
    authorized_consumer_variables: dict[str, set[str]] = {}
    operations_by_key = {item["object_key"]: item for item in local_operations.values()}
    for route in validated_routes:
        for consumer_key in route["consumer_object_keys"]:
            consumer = operations_by_key.get(consumer_key)
            if consumer is None:
                continue
            target = web_native.effective_target(consumer, "$.first_party_data_routes[].consumer")
            present, binding = first_party_binding_value(
                route,
                target,
                consumer_key,
                "$.first_party_data_routes[]",
                local_operations,
            )
            if (
                present
                and isinstance(binding, str)
                and binding.startswith("{{")
                and binding.endswith("}}")
            ):
                try:
                    bound_variables = referenced_variable_closure(binding, variable_targets)
                    authorized_variable_names.update(bound_variables)
                    authorized_consumer_variables.setdefault(consumer_key, set()).update(
                        bound_variables
                    )
                except FieldResolutionError as exc:
                    fail(str(exc))
    user_data_variables = {
        operation["name"]
        for operation in local_operations.values()
        if operation["object_type"] == "variable"
        and operation["action"] not in web_model.NON_EXECUTING_TAG_ACTIONS
        and web_native.normalized_token(
            str(web_native.effective_target(operation, "$.variable").get("type", ""))
        )
        in USER_DATA_VARIABLE_TYPES
    }
    for operation in local_operations.values():
        if operation["action"] in web_model.NON_EXECUTING_TAG_ACTIONS:
            continue
        target = web_native.effective_target(operation, "$.implementation.objects[].intended")
        if operation["object_type"] == "tag":
            try:
                fields = web_native.resolved_fields(target, local_operations, "$.first_party_scope")
                references = referenced_variable_closure(fields, variable_targets)
            except (
                FieldResolutionError,
                validation.RunValidationError,
            ) as exc:
                fail(str(exc))
                return
            configured_sensitive_fields = sensitive_fields(fields)
            approved_fields = {
                field_key(route["destination_field"])
                for route in validated_routes
                if operation["object_key"] in route["consumer_object_keys"]
            }
            if configured_sensitive_fields - approved_fields or (
                (references & user_data_variables)
                - authorized_consumer_variables.get(operation["object_key"], set())
            ):
                fail(
                    f"web tag {operation['object_key']!r} configures first-party user data "
                    "without an authorized first-party-data route"
                )
        if (
            operation["object_type"] == "variable"
            and web_native.normalized_token(str(target.get("type", ""))) in USER_DATA_VARIABLE_TYPES
        ):
            if operation["name"] not in authorized_variable_names:
                fail(
                    f"User-Provided Data variable {operation['object_key']!r} is not owned "
                    "by an authorized first-party-data route"
                )
    return operations_by_key


def validate_required_routes(*, fail, local_routes, mappings, target_id, target_requirement_ids):
    first_party_fields = {
        (item["requirement_id"], item["destination_field"]) for item in local_routes
    }
    required_first_party = {
        (item["requirement_id"], item["destination_field"])
        for item in mappings
        if item["status"] == "mapped"
        and item["destination_field"] in {"user_data", "user_id"}
        and item["requirement_id"] in target_requirement_ids
    }
    if not required_first_party <= first_party_fields:
        fail(
            f"web target {target_id!r} lacks first-party routes for "
            f"{sorted(required_first_party - first_party_fields)}"
        )
