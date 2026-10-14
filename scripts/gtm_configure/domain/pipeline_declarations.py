"""Consent topology, dedup declarations, and wire fields shared by contract and run."""

from __future__ import annotations

from typing import Any, Callable

from gtm_configure.core.contract_validation import (
    ContractValidationError,
    array,
    fail,
    object,
    text,
    unique_texts,
)
from gtm_configure.core.model import (
    CONSENT_MODES,
    CONSENT_SIGNAL_AUTHORITIES,
    DEDUP_SOURCE_TYPES,
    DEDUP_STRATEGIES,
    FIELD_FLOW_STATUSES,
    SERVER_CONSENT_MECHANISMS,
    SHAPES,
    TRANSPORT_BEHAVIORS,
    UNKNOWN_STATE_BEHAVIORS,
    WEB_CONSENT_MECHANISMS,
)
from gtm_configure.core.schemas import field_collections
from gtm_configure.domain.graph import active_tag


def validate_transport_consent(topology: dict[str, Any], fail: Callable[[str], None]) -> None:
    if topology.get("consent_mode") == "client-policy-ungated":
        enforcement = topology.get("web_enforcement", {})
        policy = enforcement.get("client_policy", {})
        if (
            enforcement.get("mechanism") != "none"
            or topology.get("signal_authority") != "none"
            or topology.get("unknown_state_behavior") != "explicit-policy"
            or topology.get("transport_behavior") != "always-transported"
            or topology.get("server_enforcement", {}).get("mechanism") != "none"
            or topology.get("server_tag_keys")
        ):
            fail(
                "client-policy-ungated requires an ungated web destination, without server transport"
            )
        if (
            not isinstance(policy, dict)
            or set(policy) != {"grade", "locator", "scope"}
            or policy.get("grade") != "approved-input"
            or any(
                not isinstance(policy.get(key), str) or not policy[key].strip()
                for key in ("locator", "scope")
            )
        ):
            fail(
                "client-policy-ungated requires explicit approved-input client_policy locator and scope"
            )
    if (
        topology.get("consent_mode") == "strict-basic"
        and topology.get("transport_behavior") == "always-transported"
        and topology.get("server_enforcement", {}).get("mechanism")
        == "incoming-google-consent-native"
    ):
        fail(
            "strict-basic cannot use always-transported Google native denied-state behavior as a no-request gate"
        )


def consent_transporters(policy, tag_policies, mode, explicit_keys=frozenset()):
    """Web policy selectors own membership; a server-bound route supplies transport."""
    members = {
        item["tag_object_key"]
        for item in tag_policies
        if item["consent_policy_id"] == policy["consent_policy_id"]
    }
    return members if mode == "pipeline" and policy["server_tag_keys"] else members & explicit_keys


def validate_consent_policies(
    raw: Any,
    requirement_ids: set[str],
    objects: dict[str, dict[str, Any]],
    targets: dict[str, dict[str, Any]],
    mode: str,
    tag_policies: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    server_tag_bindings: dict[str, list[str]] = {}
    for index, value in enumerate(array(raw, "$.consent_policies")):
        path = f"$.consent_policies[{index}]"
        topology = object(value, path)

        validate_transport_consent(topology, fail)
        topology_id = text(topology.get("consent_policy_id"), f"{path}.consent_policy_id")
        if topology_id in records:
            raise ContractValidationError(f"duplicate consent topology {topology_id!r}")
        records[topology_id] = topology
        text(topology.get("destination"), f"{path}.destination")
        if topology.get("consent_mode") not in CONSENT_MODES:
            raise ContractValidationError(f"{path}.consent_mode is unsupported")
        if topology.get("transport_behavior") not in TRANSPORT_BEHAVIORS:
            raise ContractValidationError(f"{path}.transport_behavior is unsupported")
        web = object(topology.get("web_enforcement"), f"{path}.web_enforcement")
        if web.get("mechanism") not in WEB_CONSENT_MECHANISMS:
            raise ContractValidationError(f"{path}.web_enforcement.mechanism is unsupported")
        server = object(topology.get("server_enforcement"), f"{path}.server_enforcement")
        mechanism = server.get("mechanism")
        if mechanism not in SERVER_CONSENT_MECHANISMS:
            raise ContractValidationError(f"{path}.server_enforcement.mechanism is unsupported")
        if mechanism == "server-additional-consent-check" and not server.get("template_support"):
            raise ContractValidationError(
                f"{path}.server_enforcement needs exact template_support evidence"
            )
        if topology.get("unknown_state_behavior") not in UNKNOWN_STATE_BEHAVIORS:
            raise ContractValidationError(f"{path}.unknown_state_behavior is unsupported")
        signal_authority = topology.get("signal_authority")
        if signal_authority not in CONSENT_SIGNAL_AUTHORITIES:
            raise ContractValidationError(f"{path}.signal_authority is unsupported")
        text(topology.get("signal_source"), f"{path}.signal_source")
        coverage = unique_texts(
            topology.get("event_coverage"), f"{path}.event_coverage", allow_empty=False
        )
        if len(coverage) != len(set(coverage)):
            raise ContractValidationError(f"{path}.event_coverage contains duplicates")
        server_tag_keys = unique_texts(topology.get("server_tag_keys"), f"{path}.server_tag_keys")
        transporter_tag_keys = consent_transporters(topology, tag_policies, mode)
        vendor_block = any(
            objects.get(key, {}).get("intended", {}).get("blockingTriggerId", [])
            for key in transporter_tag_keys
        )
        for key in server_tag_keys:
            item = objects.get(key)
            if item is None or not active_tag(item):
                raise ContractValidationError(
                    f"{path}.server_tag_keys must reference active server tags"
                )
            if targets[item["target_id"]]["container_type"] != "server":
                raise ContractValidationError(
                    f"{path}.server_tag_keys must reference server targets"
                )
            server_tag_bindings.setdefault(key, []).append(topology_id)
        for key in transporter_tag_keys:
            item = objects.get(key)
            if item is None or not active_tag(item):
                raise ContractValidationError(
                    f"{path}.transporter_tag_keys must reference active web tags"
                )
            if targets[item["target_id"]]["container_type"] != "web":
                raise ContractValidationError(
                    f"{path}.transporter_tag_keys must reference web targets"
                )
            blocking = item.get("intended", {}).get("blockingTriggerId", [])
            if not vendor_block and blocking:
                raise ContractValidationError(
                    f"{path} transporter tags must not carry destination vendor blocks"
                )
        if mode == "web" and server_tag_keys:
            raise ContractValidationError(f"{path} web-only consent must not bind server tags")
        if mode == "server" and transporter_tag_keys:
            raise ContractValidationError(
                f"{path} server-only consent must not bind web transporter tags"
            )
        if mode == "server" and not server_tag_keys:
            raise ContractValidationError(f"{path}.server_tag_keys must not be empty")
        if mode == "pipeline" and transporter_tag_keys and not server_tag_keys:
            raise ContractValidationError(
                f"{path} a pipeline transporter topology must bind server destination tags"
            )
        web_mechanism = web.get("mechanism")
        if transporter_tag_keys and not vendor_block:
            if web_mechanism != "transport-trigger-only":
                raise ContractValidationError(
                    f"{path} unblocked transporters require transport-trigger-only web enforcement"
                )
            if topology.get("transport_behavior") == "blocked":
                raise ContractValidationError(
                    f"{path} an unblocked transporter cannot declare blocked transport"
                )
        if vendor_block:
            if topology.get("transport_behavior") != "blocked":
                raise ContractValidationError(
                    f"{path} transporter vendor blocking requires blocked transport behavior"
                )
            if web_mechanism not in {
                "cmp-lifecycle-plus-vendor-block",
                "business-trigger-plus-vendor-block",
            }:
                raise ContractValidationError(
                    f"{path} transporter vendor blocking needs an explicit vendor-block mechanism"
                )
            if any(
                not objects[key].get("intended", {}).get("blockingTriggerId", [])
                for key in transporter_tag_keys
            ):
                raise ContractValidationError(
                    f"{path} declares transporter vendor blocking without a saved block"
                )
        if signal_authority == "third-party-cmp":
            if server_tag_keys:
                text(topology.get("server_signal_path"), f"{path}.server_signal_path")
            if topology.get("unknown_state_behavior") != "deny":
                raise ContractValidationError(
                    f"{path} third-party CMP unknown state must fail closed"
                )
            if server_tag_keys and mechanism not in {
                "server-blocking-trigger",
                "server-template-native-consent",
            }:
                raise ContractValidationError(
                    f"{path} third-party CMP destinations need a server vendor gate"
                )
        if signal_authority == "google-consent-mode" and server_tag_keys:
            if mechanism != "incoming-google-consent-native":
                raise ContractValidationError(
                    f"{path} Google consent authority requires incoming native enforcement"
                )
            if topology.get("unknown_state_behavior") != "native-product-behavior":
                raise ContractValidationError(
                    f"{path} Google native consent requires native-product-behavior"
                )
        if mechanism == "server-blocking-trigger":
            blocking_key = text(
                server.get("blocking_trigger_key"),
                f"{path}.server_enforcement.blocking_trigger_key",
            )
            trigger = objects.get(blocking_key)
            if trigger is None or trigger.get("resource_family") != "trigger":
                raise ContractValidationError(
                    f"{path}.server_enforcement.blocking_trigger_key must reference a trigger"
                )
            for tag_key in server_tag_keys:
                tag = objects[tag_key]
                if trigger["target_id"] != tag["target_id"]:
                    raise ContractValidationError(
                        f"{path} server blocking trigger must share the destination target"
                    )
                if blocking_key not in tag.get("intended", {}).get("blockingTriggerId", []):
                    raise ContractValidationError(
                        f"{path} server destination tag lacks its vendor blocking trigger"
                    )
        elif server_tag_keys:
            for tag_key in server_tag_keys:
                if objects[tag_key].get("intended", {}).get("blockingTriggerId", []):
                    raise ContractValidationError(
                        f"{path} native/no-gate server destinations must not add a blocking trigger"
                    )
        explicit_server_gate = mechanism in {
            "server-template-native-consent",
            "server-additional-consent-check",
            "server-blocking-trigger",
        }
        if (
            topology.get("transport_behavior") == "blocked"
            and explicit_server_gate
            and not topology.get("double_gate_justification")
        ):
            raise ContractValidationError(
                f"{path} duplicates a transport block with a server destination gate"
            )
        if not (
            topology.get("transport_behavior") == "blocked" and explicit_server_gate
        ) and topology.get("double_gate_justification"):
            raise ContractValidationError(
                f"{path}.double_gate_justification requires two configurable gates"
            )
    active_server_tags = {
        key
        for key, item in objects.items()
        if active_tag(item) and targets[item["target_id"]]["container_type"] == "server"
    }
    missing = sorted(active_server_tags - set(server_tag_bindings))
    duplicates = sorted(key for key, links in server_tag_bindings.items() if len(links) != 1)
    if missing or duplicates:
        raise ContractValidationError(
            "server destination tags need exactly one consent topology; "
            f"missing={missing}, duplicates={duplicates}"
        )
    return records


def validate_dedup_contracts(raw: Any, requirement_ids: set[str]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(array(raw, "$.dedup_contracts")):
        path = f"$.dedup_contracts[{index}]"
        contract = object(value, path)
        contract_id = text(contract.get("dedup_contract_id"), f"{path}.dedup_contract_id")
        if contract_id in records:
            raise ContractValidationError(f"duplicate dedup contract {contract_id!r}")
        records[contract_id] = contract
        requirement_id = text(contract.get("requirement_id"), f"{path}.requirement_id")
        if requirement_id not in requirement_ids:
            raise ContractValidationError(f"{path}.requirement_id is unknown")
        strategy = contract.get("strategy")
        source_type = contract.get("source_type")
        destination = text(contract.get("destination"), f"{path}.destination")
        text(contract.get("event_name"), f"{path}.event_name")
        if strategy not in DEDUP_STRATEGIES:
            raise ContractValidationError(f"{path}.strategy is unsupported")
        if source_type not in DEDUP_SOURCE_TYPES:
            raise ContractValidationError(f"{path}.source_type is unsupported")
        if strategy == "dual-shared-id":
            normalized_destination = "".join(
                character for character in destination.casefold() if character.isalnum()
            )
            if normalized_destination in {
                "googleads",
                "floodlight",
                "campaignmanager360",
            }:
                raise ContractValidationError(
                    f"{path} cannot apply a generic dual-shared-id contract to {destination!r}; "
                    "use the current product-specific identifier mechanism"
                )
            source_reference = text(contract.get("source_reference"), f"{path}.source_reference")
            text(contract.get("source_variable_key"), f"{path}.source_variable_key")
            browser_reference = text(contract.get("browser_reference"), f"{path}.browser_reference")
            transporter_reference = text(
                contract.get("transporter_reference"), f"{path}.transporter_reference"
            )
            unique_texts(
                contract.get("browser_consumer_keys"),
                f"{path}.browser_consumer_keys",
                allow_empty=False,
            )
            unique_texts(
                contract.get("transporter_consumer_keys"),
                f"{path}.transporter_consumer_keys",
                allow_empty=False,
            )
            server_event_data_path = text(
                contract.get("server_event_data_path"), f"{path}.server_event_data_path"
            )
            text(contract.get("browser_field"), f"{path}.browser_field")
            text(contract.get("server_field"), f"{path}.server_field")
            text(contract.get("occurrence_scope"), f"{path}.occurrence_scope")
            array(contract.get("companion_fields", []), f"{path}.companion_fields")
            if len({source_reference, browser_reference, transporter_reference}) != 1:
                raise ContractValidationError(
                    f"{path} must bind browser and transporter to one occurrence source"
                )
            if contract.get("server_generates_id") is True:
                raise ContractValidationError(f"{path} cannot regenerate the ID in the server")
            if server_event_data_path != contract.get("transported_parameter"):
                raise ContractValidationError(
                    f"{path} must consume the exact transported identifier path"
                )
        elif source_type not in {"none", "template-native"}:
            raise ContractValidationError(
                f"{path}.source_type must be 'none' or 'template-native' for {strategy!r}"
            )
    return records


def validate_field_flow(value: Any, path: str, requirement_ids: set[str]) -> dict[str, Any]:
    field = object(value, path)
    field_scope = field.get("field_scope")
    if field_scope not in {"control"} | {
        m["payload_scope"] for m in field_collections().values() if m["payload_scope"]
    }:
        raise ContractValidationError(f"{path}.field_scope is unsupported")
    text(field.get("destination_field"), f"{path}.destination_field")
    status = field.get("status")
    if status not in FIELD_FLOW_STATUSES:
        raise ContractValidationError(f"{path}.status is unsupported")
    linked = set(
        unique_texts(field.get("requirement_ids"), f"{path}.requirement_ids", allow_empty=False)
    )
    if not linked <= requirement_ids:
        raise ContractValidationError(f"{path}.requirement_ids contains unknown IDs")
    source = object(field.get("source"), f"{path}.source")
    wire = object(field.get("wire"), f"{path}.wire")
    event_data = object(field.get("event_data"), f"{path}.event_data")
    destination = object(field.get("destination"), f"{path}.destination")
    for label, node in (
        ("source", source),
        ("wire", wire),
        ("event_data", event_data),
        ("destination", destination),
    ):
        text(node.get("path"), f"{path}.{label}.path")
        if node.get("shape") not in SHAPES:
            raise ContractValidationError(f"{path}.{label}.shape is unsupported")
    shapes = {source["shape"], wire["shape"], event_data["shape"], destination["shape"]}
    if status == "proved":
        text(field.get("claiming_client_proof"), f"{path}.claiming_client_proof")
        text(field.get("receiver_owner"), f"{path}.receiver_owner")
        if len(shapes) > 1 and not field.get("transformation_owner"):
            raise ContractValidationError(f"{path} changes shape without a transformation owner")
        wire_name = wire["path"].rsplit(".", 1)[-1]
        event_data_name = event_data["path"].rsplit(".", 1)[-1]
        if wire_name == "items" and wire["shape"] != "array":
            raise ContractValidationError(f"{path}.wire items must be an array")
        if event_data_name == "items" and event_data["shape"] != "array":
            raise ContractValidationError(f"{path}.event_data items must be an array")
        if wire_name == "user_data" and wire["shape"] != "object":
            raise ContractValidationError(f"{path}.wire user_data must be an object")
        if event_data_name == "user_data" and event_data["shape"] != "object":
            raise ContractValidationError(f"{path}.event_data user_data must be an object")
    if status == "blocked" and not field.get("blocker"):
        raise ContractValidationError(f"{path}.blocker is required")
    if status == "external" and not field.get("external_dependency"):
        raise ContractValidationError(f"{path}.external_dependency is required")
    return field
