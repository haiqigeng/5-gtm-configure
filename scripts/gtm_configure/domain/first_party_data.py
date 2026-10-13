"""Web identity: shared across preparation and execution."""

from __future__ import annotations

from typing import Any

from gtm_configure.core.public_identifiers import _locate
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
    CUSTOM_CODE_TAG_TYPES,
    FIRST_PARTY_FEATURES,
    FIRST_PARTY_PRODUCTS,
    GA4_EVENT_TAG_TYPES,
    GOOGLE_ADS_CONVERSION_TAG_TYPES,
    GOOGLE_CONFIGURATION_TAG_TYPES,
    NON_EXECUTING_TAG_ACTIONS,
)
from gtm_configure.domain.web_native import (
    _configuration_value,
    _effective_target,
    _field_value,
    _normalized_token,
    _resolved_fields,
    _tag_type,
)


def _validate_first_party_feature_contract(
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
    product_types = {_tag_type(target, f"{path}.consumer") for target in consumer_targets}
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


def _first_party_binding_value(
    route: dict[str, Any],
    target: dict[str, Any],
    object_key: str,
    path: str,
    operations: dict[str, dict[str, Any]] | None = None,
) -> tuple[bool, Any]:
    """Resolve an inspected event override without guessing a native Ads parameter name."""
    native_matching = route.get("feature") == "vendor-advanced-matching" and any(
        "user_data_path" in binding for binding in route.get("consumer_bindings", [])
    )
    if route.get("feature") != "google-ads-enhanced-conversions" and not native_matching:
        if route.get("feature") == "ga4-user-provided-data":
            return _configuration_value(target, {route["destination_field"]})
        return _field_value(
            _resolved_fields(
                target,
                operations,
                path,
                event_settings=route.get("feature") != "ga4-user-id",
            ),
            {route["destination_field"]},
        )
    bindings = _array(route.get("consumer_bindings"), f"{path}.consumer_bindings")
    matches = [
        item for item in bindings if isinstance(item, dict) and item.get("object_key") == object_key
    ]
    if len(matches) != 1:
        raise RunValidationError(f"{path} needs exactly one native field binding per consumer")
    binding = matches[0]
    _text(binding.get("field_review"), f"{path}.consumer_binding.field_review")
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
            matching_name, _ = _locate(target, cell_path[:4] + ["map", "name", "value"])
        except (KeyError, TypeError, IndexError) as exc:
            raise RunValidationError(f"{path} matching row has no unique name") from exc
        if route.get("destination_field") != matching_name or [
            field.get("name") for field in route.get("fields", [])
        ] != [matching_name]:
            raise RunValidationError(
                f"{path} scalar matching binding must prove exactly its one approved field"
            )
        rows = _resolved_fields(target, operations, path).get("advancedmatchinglist", [])
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
            value, _ = _locate(target, native_path)
        except (KeyError, TypeError, IndexError) as exc:
            raise RunValidationError(
                f"{path}.native field path does not resolve uniquely in the native tag"
            ) from exc
        return value

    for activation_path in _array(binding.get("activation_paths"), f"{path}.activation_paths"):
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
    for index, binding_raw in enumerate(_array(raw, f"{path}.consumer_bindings")):
        binding_path = f"{path}.consumer_bindings[{index}]"
        binding = _object(binding_raw, binding_path)
        required = {
            "object_key",
            "product",
            "implementation",
            "tag_type",
            "template_identity",
            "evidence",
        }
        if feature == "google-ads-enhanced-conversions" or (
            feature == "vendor-advanced-matching" and "user_data_path" in binding
        ):
            required.update({"user_data_path", "activation_paths", "field_review"})
        _exact_keys(
            binding,
            binding_path,
            required=required,
        )
        object_key = _text(binding.get("object_key"), f"{binding_path}.object_key")
        if object_key not in consumers or object_key in records:
            raise RunValidationError(
                f"{binding_path}.object_key is unknown or duplicated for this route"
            )
        records.add(object_key)
        product = _normalized_token(_text(binding.get("product"), f"{binding_path}.product"))
        expected_product = FIRST_PARTY_PRODUCTS.get(feature)
        if expected_product is not None and product != _normalized_token(expected_product):
            raise RunValidationError(
                f"{binding_path}.product must identify {expected_product!r} for {feature}"
            )
        implementation = _text(binding.get("implementation"), f"{binding_path}.implementation")
        if implementation not in {"native", "installed-template"}:
            raise RunValidationError(f"{binding_path}.implementation is unsupported")
        if feature == "google-ads-enhanced-conversions" and implementation != "native":
            raise RunValidationError(f"{binding_path}.event override requires a native Ads tag")
        actual_type = _tag_type(consumer_targets[object_key], f"{binding_path}.consumer")
        declared_type = _normalized_token(
            _text(binding.get("tag_type"), f"{binding_path}.tag_type")
        )
        if declared_type != actual_type:
            raise RunValidationError(
                f"{binding_path}.tag_type differs from the bound saved tag type"
            )
        if actual_type in CUSTOM_CODE_TAG_TYPES:
            raise RunValidationError(
                f"{binding_path} cannot identify Custom HTML/Image as a product-native consumer"
            )
        template_identity = _optional_text(
            binding.get("template_identity"), f"{binding_path}.template_identity"
        )
        if implementation == "native" and template_identity is not None:
            raise RunValidationError(f"{binding_path}.native requires a null template_identity")
        if implementation == "installed-template":
            if template_identity is None:
                raise RunValidationError(
                    f"{binding_path}.installed-template requires template_identity"
                )
            if _normalized_token(template_identity) != actual_type:
                raise RunValidationError(
                    f"{binding_path}.template_identity differs from the bound saved tag type"
                )
        _unique_texts(
            binding.get("evidence"),
            f"{binding_path}.evidence",
            allow_empty=False,
        )
    if records != consumers:
        missing = sorted(consumers - records)
        raise RunValidationError(
            f"{path}.consumer_bindings must identify every consumer exactly; missing={missing}"
        )


def _validate_first_party_data_routes(
    raw: Any,
    *,
    requirement_ids: set[str],
    operations: dict[str, dict[str, Any]],
    external_dependencies: dict[str, dict[str, Any]],
    payload_mappings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    operation_by_key = {item["object_key"]: item for item in operations.values()}
    mapped_fields = {
        (item["requirement_id"], item["destination_field"])
        for item in payload_mappings
        if item["status"] == "mapped"
    }
    mapping_by_identity = {
        (item["requirement_id"], item["destination_field"]): item
        for item in payload_mappings
        if item["status"] == "mapped"
    }
    identities: set[tuple[str, str, str]] = set()
    records: list[dict[str, Any]] = []
    for index, item_raw in enumerate(_array(raw, "$.first_party_data_routes")):
        path = f"$.first_party_data_routes[{index}]"
        item = _object(item_raw, path)
        required_keys = {
            "requirement_id",
            "feature",
            "destination_field",
            "consumer_object_keys",
            "source_priority",
            "timing",
            "hashing_owner",
            "fields",
            "consent_types",
            "external_dependency_ids",
            "evidence",
        }
        optional_keys: set[str] = set()
        if item.get("feature") in {
            "google-ads-server-user-data-transport",
            "google-ads-server-user-provided-data-event",
        }:
            required_keys.add("server_consumer_object_keys")
            optional_keys.add("external_receiver_dependency_id")
        required_keys.add("consumer_bindings")
        _exact_keys(
            item,
            path,
            required=required_keys,
            optional=optional_keys,
        )
        requirement_id = _text(item.get("requirement_id"), f"{path}.requirement_id")
        if requirement_id not in requirement_ids:
            raise RunValidationError(f"{path}.requirement_id is unknown")
        feature = _text(item.get("feature"), f"{path}.feature")
        if feature not in FIRST_PARTY_FEATURES:
            raise RunValidationError(f"{path}.feature has unsupported value {feature!r}")
        destination_field = _text(
            item.get("destination_field"),
            f"{path}.destination_field",
        )
        if (requirement_id, destination_field) not in mapped_fields:
            raise RunValidationError(
                f"{path} must bind to a mapped payload field {requirement_id}::{destination_field}"
            )
        identity = (
            requirement_id,
            feature,
            destination_field if feature == "vendor-advanced-matching" else "",
        )
        if identity in identities:
            raise RunValidationError(f"duplicate first-party-data route {identity!r}")
        identities.add(identity)
        consumers = set(
            _unique_texts(
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
            target = _effective_target(operation, f"{path}.consumer_object_keys")
            present, configured_value = _first_party_binding_value(
                item, target, object_key, path, operations
            )
            if not present:
                raise RunValidationError(
                    f"{path}.consumer {object_key!r} does not configure {destination_field!r}"
                )
            expected_binding = mapping_by_identity[(requirement_id, destination_field)].get(
                "gtm_resolution"
            )
            if expected_binding is not None and configured_value != expected_binding:
                raise RunValidationError(
                    f"{path}.consumer {object_key!r} {destination_field!r} binding differs "
                    "from the approved field binding"
                )
            if feature == "vendor-advanced-matching" and any(
                "user_data_path" in binding for binding in item.get("consumer_bindings", [])
            ):
                mapping = mapping_by_identity[(requirement_id, destination_field)]
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
        source_priority = _text(item.get("source_priority"), f"{path}.source_priority")
        if source_priority not in {
            "data-layer",
            "controlled-javascript",
            "dom",
            "automatic",
        }:
            raise RunValidationError(f"{path}.source_priority is unsupported")
        timing = _text(item.get("timing"), f"{path}.timing")
        if timing not in {"tag-wide", "same-event", "prior-page"}:
            raise RunValidationError(f"{path}.timing is unsupported")
        hashing_owner = _text(item.get("hashing_owner"), f"{path}.hashing_owner")
        if hashing_owner not in {"not-applicable", "native-raw", "prehashed-sha256"}:
            raise RunValidationError(f"{path}.hashing_owner is unsupported")
        fields = _array(item.get("fields"), f"{path}.fields")
        if not fields:
            raise RunValidationError(f"{path}.fields must not be empty")
        field_names: set[str] = set()
        for field_index, field_raw in enumerate(fields):
            field_path = f"{path}.fields[{field_index}]"
            field = _object(field_raw, field_path)
            _exact_keys(
                field,
                field_path,
                required={"name", "source", "normalization", "empty_behavior"},
            )
            name = _text(field.get("name"), f"{field_path}.name")
            if name in field_names:
                raise RunValidationError(f"{path}.fields contains duplicate field {name!r}")
            field_names.add(name)
            _text(field.get("source"), f"{field_path}.source")
            _unique_texts(field.get("normalization"), f"{field_path}.normalization")
            if field.get("empty_behavior") != "omit":
                raise RunValidationError(f"{field_path}.empty_behavior must be 'omit'")
        consent_types = set(_unique_texts(item.get("consent_types"), f"{path}.consent_types"))
        dependency_ids = set(
            _unique_texts(
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
        _unique_texts(item.get("evidence"), f"{path}.evidence", allow_empty=False)
        _validate_first_party_feature_contract(
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
