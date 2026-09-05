#!/usr/bin/env python3
"""Validate the current configure-gtm configuration-contract@7.0."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requirement_validation as requirement_support
import run_validation_web as web_support
from action_contract import validate_action_contract
from event_semantics import approved_event_name
from redaction import sensitive_paths
from resource_registry import (
    ResourceRegistryError,
    is_configuration_settings_mutation,
    semantic_object_key,
    validate_target_family,
)
from run_model import (
    ACTIONS,
    CONSENT_MODES,
    CONSENT_SIGNAL_AUTHORITIES,
    CONTRACT_SCHEMA_VERSION,
    DEDUP_SOURCE_TYPES,
    DEDUP_STRATEGIES,
    DELTA_ACTIONS,
    FIELD_FLOW_STATUSES,
    MUTATING_ACTIONS,
    RUN_MODES,
    SERVER_CONSENT_MECHANISMS,
    SHAPES,
    TARGET_TYPES,
    TRANSPORT_BEHAVIORS,
    UNKNOWN_STATE_BEHAVIORS,
    WEB_CONSENT_MECHANISMS,
)
from strict_json import StrictJsonError, load_json
from web_domain_validation import validate_web_domain

_WEB_BUILT_IN_TRIGGER_IDS = {"2147479553", "2147479572", "2147479573"}
_MAX_OFFICIAL_EVIDENCE_AGE_DAYS = 365


SCHEMA_VERSION = CONTRACT_SCHEMA_VERSION
ROUTES = requirement_support.ROUTES
REQUIREMENT_KINDS = requirement_support.REQUIREMENT_KINDS
EVIDENCE_GRADES = requirement_support.EVIDENCE_GRADES
OBJECT_RESOURCE_FAMILIES = requirement_support.OBJECT_RESOURCE_FAMILIES | {
    "client",
    "transformation",
}
HIGH_IMPACT_RESOURCE_FAMILIES = {
    "client",
    "container setting",
    "destination",
    "environment",
    "google tag configuration",
    "template",
    "transformation",
    "zone",
}
TOP_LEVEL_KEYS = {
    "schema_version",
    "mode",
    "route",
    "scope",
    "requirements",
    "targets",
    "pipelines",
    "consent_topologies",
    "dedup_contracts",
    "execution_topologies",
    "page_view_decisions",
    "first_party_data_routes",
    "inventory_dispositions",
    "implementation",
    "evidence",
    "external_dependencies",
}


class ContractValidationError(ValueError):
    """Raised when the current contract cannot safely authorize deterministic materialization."""

    def __init__(self, message: str, *, error_code: str = "invalid_contract") -> None:
        super().__init__(message)
        self.error_code = error_code


def _fail(message: str) -> None:
    raise ContractValidationError(message)


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractValidationError(f"{path} must be an object")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractValidationError(f"{path} must be an array")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{path} must be a non-empty string")
    return value.strip()


def _unique_texts(value: Any, path: str, *, allow_empty: bool = True) -> list[str]:
    items = [_text(item, f"{path}[]") for item in _array(value, path)]
    if not allow_empty and not items:
        raise ContractValidationError(f"{path} must not be empty")
    if len(set(items)) != len(items):
        raise ContractValidationError(f"{path} contains duplicate values")
    return items


def _reference_values(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {item for child in value.values() for item in _reference_values(child)}
    if isinstance(value, list):
        return {item for child in value for item in _reference_values(child)}
    return {value} if isinstance(value, str) else set()


def _active_tag(item: dict[str, Any]) -> bool:
    intended = item.get("intended") if isinstance(item.get("intended"), dict) else {}
    return (
        item.get("resource_family") == "tag"
        and item.get("action") not in {"remove", "pause"}
        and intended.get("paused") is not True
    )


def _reference_name(value: str) -> str | None:
    match = re.fullmatch(r"\{\{\s*(.+?)\s*\}\}", value)
    return match.group(1) if match else None


def _authority(value: Any, path: str, *, approved: bool = False) -> dict[str, Any]:
    authority = _object(value, path)
    grade = _text(authority.get("grade"), f"{path}.grade")
    if grade not in EVIDENCE_GRADES:
        raise ContractValidationError(f"{path}.grade has unsupported value {grade!r}")
    if approved and grade != "approved-input":
        raise ContractValidationError(f"{path}.grade must be 'approved-input'")
    _text(authority.get("locator"), f"{path}.locator")
    return authority


def _validate_scope_and_requirements(contract: dict[str, Any], route: str) -> set[str]:
    scope = _object(contract["scope"], "$.scope")
    partitions = {
        name: set(_unique_texts(scope.get(name), f"$.scope.{name}"))
        for name in ("included", "reference_only", "excluded")
    }
    for left, right in (
        ("included", "reference_only"),
        ("included", "excluded"),
        ("reference_only", "excluded"),
    ):
        overlap = sorted(partitions[left] & partitions[right])
        if overlap:
            raise ContractValidationError(
                f"$.scope.{left} and $.scope.{right} overlap: {', '.join(overlap)}"
            )
    requirement_ids: set[str] = set()
    for index, raw in enumerate(_array(contract["requirements"], "$.requirements")):
        try:
            requirement_id = requirement_support.validate_requirement(
                raw,
                index=index,
                route=route,
            )
        except requirement_support.ContractValidationError as exc:
            raise ContractValidationError(str(exc)) from exc
        if requirement_id in requirement_ids:
            raise ContractValidationError(f"duplicate requirement id {requirement_id!r}")
        requirement_ids.add(requirement_id)
    if requirement_ids != partitions["included"]:
        raise ContractValidationError(
            "$.scope.included must equal the IDs represented in $.requirements"
        )
    return requirement_ids


def _validate_targets(raw: Any, mode: str) -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(_array(raw, "$.targets")):
        path = f"$.targets[{index}]"
        target = _object(value, path)
        target_id = _text(target.get("target_id"), f"{path}.target_id")
        if "::" in target_id:
            raise ContractValidationError(f"{path}.target_id must not contain '::'")
        if target_id in targets:
            raise ContractValidationError(f"duplicate target_id {target_id!r}")
        container_type = _text(target.get("container_type"), f"{path}.container_type")
        if container_type not in TARGET_TYPES:
            raise ContractValidationError(f"{path}.container_type has unsupported value")
        for field in ("account_id", "container_id", "workspace_id"):
            _text(target.get(field), f"{path}.{field}")
        _authority(target.get("authority"), f"{path}.authority", approved=True)
        targets[target_id] = target
    if not targets:
        raise ContractValidationError("$.targets must not be empty")
    target_types = {target["container_type"] for target in targets.values()}
    if mode == "web" and target_types != {"web"}:
        raise ContractValidationError("web mode permits only web targets")
    if mode == "server" and target_types != {"server"}:
        raise ContractValidationError("server mode permits only server targets")
    if mode == "pipeline" and target_types != TARGET_TYPES:
        raise ContractValidationError(
            "pipeline mode requires at least one web and one server target"
        )
    return targets


def _object_is_high_impact(item: dict[str, Any]) -> bool:
    family = item["resource_family"]
    if is_configuration_settings_mutation(item):
        return True
    if item["action"] in {"remove", "replace", "pause", "unpause"}:
        return True
    if family not in HIGH_IMPACT_RESOURCE_FAMILIES:
        return False
    if family == "client" and item["action"] == "reuse":
        return False
    if family == "transformation" and item.get("scope") == "single-destination":
        return False
    return item["action"] in MUTATING_ACTIONS


def _validate_objects(
    raw: Any,
    targets: dict[str, dict[str, Any]],
    requirements: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    requirement_ids = set(requirements)
    objects: dict[str, dict[str, Any]] = {}
    aliases: dict[str, str] = {}
    for index, value in enumerate(_array(raw, "$.implementation.objects")):
        path = f"$.implementation.objects[{index}]"
        item = _object(value, path)
        target_id = _text(item.get("target_id"), f"{path}.target_id")
        if target_id not in targets:
            raise ContractValidationError(f"{path}.target_id references an unknown target")
        action = _text(item.get("action"), f"{path}.action")
        if action not in ACTIONS:
            raise ContractValidationError(f"{path}.action has unsupported value {action!r}")
        family = _text(item.get("resource_family"), f"{path}.resource_family")
        try:
            family = validate_target_family(targets[target_id]["container_type"], family)
        except ResourceRegistryError as exc:
            raise ContractValidationError(f"{path}: {exc}") from exc
        item["resource_family"] = family
        if action in {"pause", "unpause"} and family != "tag":
            raise ContractValidationError(f"{path}.{action} is supported only for tags")
        name = _text(item.get("name"), f"{path}.name")
        key = semantic_object_key(target_id, family, name)
        if key in objects:
            raise ContractValidationError(f"duplicate object identity {key!r}")
        alias = _text(item.get("object_key", key), f"{path}.object_key")
        if alias != key:
            raise ContractValidationError(f"{path}.object_key must equal {key!r}")
        _text(item.get("justification"), f"{path}.justification")
        links = set(_unique_texts(item.get("requirement_ids", []), f"{path}.requirement_ids"))
        unknown = sorted(links - requirement_ids)
        if unknown:
            raise ContractValidationError(
                f"{path}.requirement_ids contains unknown IDs: {', '.join(unknown)}"
            )
        evidence = set(_unique_texts(item.get("evidence"), f"{path}.evidence", allow_empty=False))
        if not evidence <= EVIDENCE_GRADES:
            raise ContractValidationError(f"{path}.evidence contains an unsupported grade")
        if action in MUTATING_ACTIONS:
            if not links:
                raise ContractValidationError(
                    f"{path}.requirement_ids must bind every mutation to approved scope"
                )
            if "approved-input" not in evidence:
                raise ContractValidationError(
                    f"{path}.evidence needs 'approved-input' mutation authority"
                )
        if (
            action in {"reuse", "untouched", *DELTA_ACTIONS}
            and "container-confirmed" not in evidence
        ):
            raise ContractValidationError(f"{path}.evidence needs 'container-confirmed'")
        if action in DELTA_ACTIONS:
            pre_change = _object(item.get("pre_change"), f"{path}.pre_change")
            if not pre_change:
                raise ContractValidationError(f"{path}.pre_change must not be empty")
        if action in {"create", "update", "replace"}:
            intended = _object(item.get("intended"), f"{path}.intended")
            if not intended:
                raise ContractValidationError(f"{path}.intended must not be empty")
        if family == "client" and action in {"create", "update", "replace", "reuse"}:
            intended = _object(item.get("intended"), f"{path}.intended")
            for field in ("type", "claim_criteria"):
                _text(intended.get(field), f"{path}.intended.{field}")
            priority = intended.get("priority")
            if isinstance(priority, bool) or not isinstance(priority, int):
                raise ContractValidationError(f"{path}.intended.priority must be an integer")
        risk = item.get("risk", "routine")
        if risk not in {"routine", "high-impact"}:
            raise ContractValidationError(f"{path}.risk has unsupported value {risk!r}")
        expected_high = _object_is_high_impact(item)
        if expected_high and risk != "high-impact":
            raise ContractValidationError(f"{path}.risk must be 'high-impact'")
        validate_action_contract(
            item,
            path=path,
            fail=_fail,
            authority_locators={requirements[value]["authority"]["locator"] for value in links},
        )
        objects[key] = item
        aliases[key] = key
    for key, item in objects.items():
        dependencies = _unique_texts(
            item.get("depends_on", []), f"$.implementation.objects[{key!r}].depends_on"
        )
        for dependency in dependencies:
            if dependency not in aliases:
                raise ContractValidationError(
                    f"object {key!r} depends on unknown object {dependency!r}"
                )
            if dependency == key:
                raise ContractValidationError(f"object {key!r} cannot depend on itself")
    _reject_cycles({key: item.get("depends_on", []) for key, item in objects.items()}, "objects")
    return objects, aliases


def _reject_cycles(graph: dict[str, list[str]], label: str) -> None:
    remaining = {key: len(value) for key, value in graph.items()}
    dependents: dict[str, list[str]] = {key: [] for key in graph}
    for key, dependencies in graph.items():
        for dependency in dependencies:
            dependents.setdefault(dependency, []).append(key)
    ready = [key for key, count in remaining.items() if count == 0]
    seen = 0
    while ready:
        key = ready.pop()
        seen += 1
        for dependent in dependents.get(key, []):
            remaining[dependent] -= 1
            if remaining[dependent] == 0:
                ready.append(dependent)
    if seen != len(graph):
        raise ContractValidationError(f"{label} dependency graph contains a cycle")


def _trigger_accepts_event(trigger: dict[str, Any], event_name: str) -> bool:
    from event_semantics import trigger_accepts_event

    return trigger_accepts_event(trigger.get("intended", {}), event_name)


def _validate_server_object_graph(
    objects: dict[str, dict[str, Any]],
    targets: dict[str, dict[str, Any]],
    requirements: dict[str, dict[str, Any]],
    pipelines: list[dict[str, Any]],
) -> None:
    server_tags = {
        key: item
        for key, item in objects.items()
        if _active_tag(item) and targets[item["target_id"]]["container_type"] == "server"
    }
    trigger_by_key = {
        key: item
        for key, item in objects.items()
        if item.get("resource_family") == "trigger"
        and targets[item["target_id"]]["container_type"] == "server"
    }
    tag_triggers: dict[str, list[dict[str, Any]]] = {}
    for key, tag in server_tags.items():
        path = f"server tag {key!r}"
        intended = _object(tag.get("intended"), f"{path}.intended")
        firing = _unique_texts(
            intended.get("firingTriggerId"), f"{path}.intended.firingTriggerId", allow_empty=False
        )
        blocking = _unique_texts(
            intended.get("blockingTriggerId", []), f"{path}.intended.blockingTriggerId"
        )
        if set(firing) & set(blocking):
            raise ContractValidationError(f"{path} reuses one trigger for firing and blocking")
        resolved = []
        for reference in firing + blocking:
            if reference in _WEB_BUILT_IN_TRIGGER_IDS:
                raise ContractValidationError(f"{path} uses a web built-in trigger")
            trigger = trigger_by_key.get(reference)
            if trigger is None or trigger["target_id"] != tag["target_id"]:
                raise ContractValidationError(
                    f"{path} trigger references must resolve inside the server target"
                )
            if reference not in tag.get("depends_on", []):
                raise ContractValidationError(
                    f"{path} must depend on every firing and blocking trigger"
                )
            if reference in firing:
                resolved.append(trigger)
        tag_triggers[key] = resolved

    expected_events: dict[str, set[str]] = {key: set() for key in server_tags}
    for pipeline in pipelines:
        for flow in pipeline.get("event_flows", []):
            for key in flow.get("server_consumer_keys", []):
                if key in expected_events:
                    expected_events[key].add(flow["transported_event"])
    for key, tag in server_tags.items():
        from event_semantics import configured_event_name

        literal = configured_event_name(tag.get("intended", {}))
        approved_names = {
            requirements[requirement_id].get("event_name")
            for requirement_id in tag.get("requirement_ids", [])
            if requirement_id in requirements
        } - {None}
        if (
            tag.get("intended", {}).get("type") == "gaawc"
            and literal is not None
            and approved_names
            and literal not in approved_names
        ):
            raise ContractValidationError(
                f"server tag {key!r} configured event {literal!r} differs from approved event names"
            )
        if not expected_events[key]:
            for requirement_id in tag.get("requirement_ids", []):
                requirement = requirements.get(requirement_id, {})
                event_name = approved_event_name(requirement)
                if event_name:
                    expected_events[key].add(event_name)
        for event_name in expected_events[key]:
            if not any(
                _trigger_accepts_event(trigger, event_name) for trigger in tag_triggers[key]
            ):
                raise ContractValidationError(
                    f"server tag {key!r} has no firing trigger for {event_name!r}"
                )


def _validate_consent_topologies(
    raw: Any,
    requirement_ids: set[str],
    objects: dict[str, dict[str, Any]],
    targets: dict[str, dict[str, Any]],
    mode: str,
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    server_tag_bindings: dict[str, list[str]] = {}
    for index, value in enumerate(_array(raw, "$.consent_topologies")):
        path = f"$.consent_topologies[{index}]"
        topology = _object(value, path)
        from run_validation_pipeline import validate_transport_consent

        validate_transport_consent(topology, _fail)
        topology_id = _text(topology.get("consent_topology_id"), f"{path}.consent_topology_id")
        if topology_id in records:
            raise ContractValidationError(f"duplicate consent topology {topology_id!r}")
        records[topology_id] = topology
        _text(topology.get("destination"), f"{path}.destination")
        if topology.get("consent_mode") not in CONSENT_MODES:
            raise ContractValidationError(f"{path}.consent_mode is unsupported")
        links = set(
            _unique_texts(
                topology.get("requirement_ids"), f"{path}.requirement_ids", allow_empty=False
            )
        )
        if not links <= requirement_ids:
            raise ContractValidationError(f"{path}.requirement_ids contains unknown IDs")
        if topology.get("transport_behavior") not in TRANSPORT_BEHAVIORS:
            raise ContractValidationError(f"{path}.transport_behavior is unsupported")
        web = _object(topology.get("web_enforcement"), f"{path}.web_enforcement")
        if web.get("mechanism") not in WEB_CONSENT_MECHANISMS:
            raise ContractValidationError(f"{path}.web_enforcement.mechanism is unsupported")
        server = _object(topology.get("server_enforcement"), f"{path}.server_enforcement")
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
        _text(topology.get("signal_source"), f"{path}.signal_source")
        coverage = _unique_texts(
            topology.get("event_coverage"), f"{path}.event_coverage", allow_empty=False
        )
        if len(coverage) != len(set(coverage)):
            raise ContractValidationError(f"{path}.event_coverage contains duplicates")
        if topology.get("intentional_double_gate") is True and not topology.get(
            "double_gate_justification"
        ):
            raise ContractValidationError(f"{path}.double_gate_justification is required")
        server_tag_keys = _unique_texts(topology.get("server_tag_keys"), f"{path}.server_tag_keys")
        transporter_tag_keys = _unique_texts(
            topology.get("transporter_tag_keys"), f"{path}.transporter_tag_keys"
        )
        vendor_block = topology.get("transporter_destination_vendor_block")
        if not isinstance(vendor_block, bool):
            raise ContractValidationError(
                f"{path}.transporter_destination_vendor_block must be boolean"
            )
        for key in server_tag_keys:
            item = objects.get(key)
            if item is None or not _active_tag(item):
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
            if item is None or not _active_tag(item):
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
        if mode == "web" and (server_tag_keys or transporter_tag_keys):
            raise ContractValidationError(
                f"{path} web-only consent must not bind server or transporter tags"
            )
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
                _text(topology.get("server_signal_path"), f"{path}.server_signal_path")
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
            blocking_key = _text(
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
            and topology.get("intentional_double_gate") is not True
        ):
            raise ContractValidationError(
                f"{path} duplicates a transport block with a server destination gate"
            )
        if (
            not (topology.get("transport_behavior") == "blocked" and explicit_server_gate)
            and topology.get("intentional_double_gate") is True
        ):
            raise ContractValidationError(
                f"{path}.intentional_double_gate is true without two configurable gates"
            )
    active_server_tags = {
        key
        for key, item in objects.items()
        if _active_tag(item) and targets[item["target_id"]]["container_type"] == "server"
    }
    missing = sorted(active_server_tags - set(server_tag_bindings))
    duplicates = sorted(key for key, links in server_tag_bindings.items() if len(links) != 1)
    if missing or duplicates:
        raise ContractValidationError(
            "server destination tags need exactly one consent topology; "
            f"missing={missing}, duplicates={duplicates}"
        )
    return records


def _validate_dedup_contracts(raw: Any, requirement_ids: set[str]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(_array(raw, "$.dedup_contracts")):
        path = f"$.dedup_contracts[{index}]"
        contract = _object(value, path)
        contract_id = _text(contract.get("dedup_contract_id"), f"{path}.dedup_contract_id")
        if contract_id in records:
            raise ContractValidationError(f"duplicate dedup contract {contract_id!r}")
        records[contract_id] = contract
        requirement_id = _text(contract.get("requirement_id"), f"{path}.requirement_id")
        if requirement_id not in requirement_ids:
            raise ContractValidationError(f"{path}.requirement_id is unknown")
        strategy = contract.get("strategy")
        source_type = contract.get("source_type")
        destination = _text(contract.get("destination"), f"{path}.destination")
        _text(contract.get("event_name"), f"{path}.event_name")
        if strategy not in DEDUP_STRATEGIES:
            raise ContractValidationError(f"{path}.strategy is unsupported")
        if source_type not in DEDUP_SOURCE_TYPES:
            raise ContractValidationError(f"{path}.source_type is unsupported")
        if strategy == "dual-shared-id":
            normalized_destination = "".join(
                character for character in destination.casefold() if character.isalnum()
            )
            if normalized_destination in {"googleads", "floodlight", "campaignmanager360"}:
                raise ContractValidationError(
                    f"{path} cannot apply a generic dual-shared-id contract to {destination!r}; "
                    "use the current product-specific identifier mechanism"
                )
            source_reference = _text(contract.get("source_reference"), f"{path}.source_reference")
            _text(contract.get("source_variable_key"), f"{path}.source_variable_key")
            browser_reference = _text(
                contract.get("browser_reference"), f"{path}.browser_reference"
            )
            transporter_reference = _text(
                contract.get("transporter_reference"), f"{path}.transporter_reference"
            )
            _unique_texts(
                contract.get("browser_consumer_keys"),
                f"{path}.browser_consumer_keys",
                allow_empty=False,
            )
            _unique_texts(
                contract.get("transporter_consumer_keys"),
                f"{path}.transporter_consumer_keys",
                allow_empty=False,
            )
            server_event_data_path = _text(
                contract.get("server_event_data_path"), f"{path}.server_event_data_path"
            )
            _text(contract.get("browser_field"), f"{path}.browser_field")
            _text(contract.get("server_field"), f"{path}.server_field")
            _text(contract.get("occurrence_scope"), f"{path}.occurrence_scope")
            _array(contract.get("companion_fields", []), f"{path}.companion_fields")
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


def _validate_field_flow(value: Any, path: str, requirement_ids: set[str]) -> dict[str, Any]:
    field = _object(value, path)
    field_scope = field.get("field_scope")
    if field_scope not in {"event-parameter", "user-property", "item-parameter", "control"}:
        raise ContractValidationError(f"{path}.field_scope is unsupported")
    _text(field.get("destination_field"), f"{path}.destination_field")
    status = field.get("status")
    if status not in FIELD_FLOW_STATUSES:
        raise ContractValidationError(f"{path}.status is unsupported")
    linked = set(
        _unique_texts(field.get("requirement_ids"), f"{path}.requirement_ids", allow_empty=False)
    )
    if not linked <= requirement_ids:
        raise ContractValidationError(f"{path}.requirement_ids contains unknown IDs")
    source = _object(field.get("source"), f"{path}.source")
    wire = _object(field.get("wire"), f"{path}.wire")
    event_data = _object(field.get("event_data"), f"{path}.event_data")
    destination = _object(field.get("destination"), f"{path}.destination")
    for label, node in (
        ("source", source),
        ("wire", wire),
        ("event_data", event_data),
        ("destination", destination),
    ):
        _text(node.get("path"), f"{path}.{label}.path")
        if node.get("shape") not in SHAPES:
            raise ContractValidationError(f"{path}.{label}.shape is unsupported")
    shapes = {source["shape"], wire["shape"], event_data["shape"], destination["shape"]}
    if status == "proved":
        _text(field.get("claiming_client_proof"), f"{path}.claiming_client_proof")
        _text(field.get("receiver_owner"), f"{path}.receiver_owner")
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


def _validate_pipelines(
    raw: Any,
    mode: str,
    targets: dict[str, dict[str, Any]],
    objects: dict[str, dict[str, Any]],
    requirement_ids: set[str],
    requirements: dict[str, dict[str, Any]],
    consent_topologies: dict[str, dict[str, Any]],
    dedup_contracts: dict[str, dict[str, Any]],
) -> None:
    pipelines = _array(raw, "$.pipelines")
    if mode != "pipeline" and pipelines:
        raise ContractValidationError("$.pipelines must be empty outside pipeline mode")
    if mode != "pipeline" and dedup_contracts:
        raise ContractValidationError("$.dedup_contracts must be empty outside pipeline mode")
    if mode == "pipeline" and not pipelines:
        raise ContractValidationError("pipeline mode requires at least one pipeline")
    seen: set[str] = set()
    receiver_claims: dict[tuple[str, str], set[str]] = {}
    for index, value in enumerate(pipelines):
        path = f"$.pipelines[{index}]"
        pipeline = _object(value, path)
        pipeline_id = _text(pipeline.get("pipeline_id"), f"{path}.pipeline_id")
        if pipeline_id in seen:
            raise ContractValidationError(f"duplicate pipeline_id {pipeline_id!r}")
        seen.add(pipeline_id)
        senders = _unique_texts(
            pipeline.get("sending_target_ids"), f"{path}.sending_target_ids", allow_empty=False
        )
        receiver = _text(pipeline.get("receiving_target_id"), f"{path}.receiving_target_id")
        if any(
            target not in targets or targets[target]["container_type"] != "web"
            for target in senders
        ):
            raise ContractValidationError(f"{path}.sending_target_ids must reference web targets")
        if receiver not in targets or targets[receiver]["container_type"] != "server":
            raise ContractValidationError(
                f"{path}.receiving_target_id must reference a server target"
            )
        _text(pipeline.get("request_class"), f"{path}.request_class")
        transport_owner = _text(pipeline.get("transport_owner"), f"{path}.transport_owner")
        if (
            transport_owner not in objects
            or objects[transport_owner]["resource_family"] != "tag"
            or objects[transport_owner]["target_id"] not in senders
        ):
            raise ContractValidationError(f"{path}.transport_owner must reference a sender web tag")
        endpoint_reference = _text(pipeline.get("endpoint_reference"), f"{path}.endpoint_reference")
        resolved_endpoint = web_support._normalize_transport_endpoint(
            web_support._resolve_constant_reference(
                endpoint_reference, objects, f"{path}.endpoint_reference"
            ),
            f"{path}.endpoint_reference",
        )
        owner_endpoint = web_support._configured_transport_endpoint(
            objects[transport_owner], objects, f"{path}.transport_owner"
        )
        if owner_endpoint != resolved_endpoint:
            raise ContractValidationError(
                f"{path}.endpoint_reference differs from its transport owner"
            )
        owner_destinations = web_support._configured_destinations(
            objects[transport_owner]["intended"], objects, f"{path}.transport_owner"
        )
        claiming = _object(pipeline.get("claiming_client"), f"{path}.claiming_client")
        client_key = _text(claiming.get("object_key"), f"{path}.claiming_client.object_key")
        if client_key not in objects or objects[client_key]["resource_family"] != "client":
            raise ContractValidationError(f"{path}.claiming_client must reference a Client object")
        if objects[client_key]["target_id"] != receiver:
            raise ContractValidationError(f"{path}.claiming_client must belong to the receiver")
        claim_criteria = _text(
            claiming.get("claim_criteria"), f"{path}.claiming_client.claim_criteria"
        )
        client_intended = _object(
            objects[client_key].get("intended"),
            f"{path}.claiming_client.referenced_client_intended",
        )
        if client_intended.get("claim_criteria") != claim_criteria:
            raise ContractValidationError(
                f"{path}.claiming_client claim criteria differs from the verified Client state"
            )
        claim_key = (receiver, pipeline["request_class"])
        receiver_claims.setdefault(claim_key, set()).add(client_key)
        page_view = _object(pipeline.get("page_view_ownership"), f"{path}.page_view_ownership")
        if page_view.get("occurrence") != "initial-page-load":
            raise ContractValidationError(
                f"{path}.page_view_ownership.occurrence must be 'initial-page-load'"
            )
        page_owner = _text(page_view.get("owner"), f"{path}.page_view_ownership.owner")
        if (
            page_owner not in objects
            or objects[page_owner]["resource_family"] != "tag"
            or objects[page_owner]["target_id"] not in senders
        ):
            raise ContractValidationError(
                f"{path}.page_view_ownership.owner must reference a sender web tag"
            )
        owner_target = _object(
            objects[page_owner].get("intended"),
            f"{path}.page_view_ownership.owner_intended",
        )
        owner_type = web_support._tag_type(owner_target, path)
        if owner_type in web_support.GOOGLE_CONFIGURATION_TAG_TYPES:
            if page_view.get("send_page_view") not in {True, False}:
                raise ContractValidationError(
                    f"{path}.page_view_ownership.send_page_view must be boolean for a Google tag"
                )
            if (
                web_support._send_page_view_value(owner_target, path, objects)
                != page_view["send_page_view"]
            ):
                raise ContractValidationError(
                    f"{path}.page_view_ownership differs from the bound Google tag"
                )
        elif page_view.get("send_page_view") is not None:
            raise ContractValidationError(
                f"{path}.page_view_ownership.send_page_view must be null for a non-Google sender"
            )
        event_flows = _array(pipeline.get("event_flows"), f"{path}.event_flows")
        if not event_flows:
            raise ContractValidationError(f"{path}.event_flows must not be empty")
        for flow_index, flow_value in enumerate(event_flows):
            flow_path = f"{path}.event_flows[{flow_index}]"
            flow = _object(flow_value, flow_path)
            requirement_id = _text(flow.get("requirement_id"), f"{flow_path}.requirement_id")
            if requirement_id not in requirement_ids:
                raise ContractValidationError(f"{flow_path}.requirement_id is unknown")
            source_event = _text(flow.get("source_event"), f"{flow_path}.source_event")
            requirement = requirements[requirement_id]
            approved_source_event = approved_event_name(requirement)
            if approved_source_event and source_event != approved_source_event:
                raise ContractValidationError(
                    f"{flow_path}.source_event differs from its approved requirement"
                )
            _text(flow.get("transported_event"), f"{flow_path}.transported_event")
            consumers = _unique_texts(
                flow.get("server_consumer_keys"),
                f"{flow_path}.server_consumer_keys",
                allow_empty=False,
            )
            for consumer in consumers:
                if (
                    consumer not in objects
                    or objects[consumer]["target_id"] != receiver
                    or objects[consumer]["resource_family"] != "tag"
                ):
                    raise ContractValidationError(
                        f"{flow_path}.server_consumer_keys must reference receiver tags"
                    )
        field_flows = []
        field_flow_identities: set[tuple[str, str, str]] = set()
        flow_requirement_ids = {flow["requirement_id"] for flow in event_flows}
        for field_index, field_value in enumerate(
            _array(pipeline.get("field_flows"), f"{path}.field_flows")
        ):
            field_path = f"{path}.field_flows[{field_index}]"
            field = _validate_field_flow(field_value, field_path, requirement_ids)
            if not set(field["requirement_ids"]) <= flow_requirement_ids:
                raise ContractValidationError(
                    f"{field_path}.requirement_ids must belong to this pipeline's event flows"
                )
            for requirement_id in field["requirement_ids"]:
                identity = (
                    requirement_id,
                    field["field_scope"],
                    field["destination_field"],
                )
                if identity in field_flow_identities:
                    raise ContractValidationError(
                        f"{field_path} duplicates pipeline field flow {identity!r}"
                    )
                field_flow_identities.add(identity)
            if field.get("status") == "proved":
                receiver_owner = field["receiver_owner"]
                receiver_operation = objects.get(receiver_owner)
                if (
                    receiver_operation is None
                    or receiver_operation.get("resource_family") != "tag"
                    or receiver_operation.get("target_id") != receiver
                ):
                    raise ContractValidationError(
                        f"{field_path}.receiver_owner must reference a receiver server tag"
                    )
                if not set(field["requirement_ids"]) <= set(
                    receiver_operation.get("requirement_ids", [])
                ):
                    raise ContractValidationError(
                        f"{field_path}.receiver_owner does not cover the field requirements"
                    )
                transformation_owner = field.get("transformation_owner")
                if transformation_owner:
                    transformation = objects.get(transformation_owner)
                    if (
                        transformation is None
                        or transformation.get("resource_family") != "transformation"
                        or transformation.get("target_id") != receiver
                    ):
                        raise ContractValidationError(
                            f"{field_path}.transformation_owner must reference a receiver "
                            "Transformation"
                        )
                    elif transformation.get("intended", {}).get("mode") == "allow" and field.get(
                        "wire", {}
                    ).get("path") not in set(
                        transformation.get("intended", {}).get("allowed_parameters", [])
                    ):
                        raise ContractValidationError(
                            f"{field_path}.transformation_owner allowlist removes the proved "
                            "wire field"
                        )
            field_flows.append(field)
        topology_links = _unique_texts(
            pipeline.get("consent_topology_ids"),
            f"{path}.consent_topology_ids",
            allow_empty=False,
        )
        all_server_consumers = {
            key for flow in event_flows for key in flow.get("server_consumer_keys", [])
        }
        bound_server_consumers: set[str] = set()
        for topology_id in topology_links:
            if topology_id not in consent_topologies:
                raise ContractValidationError(f"{path} references unknown consent topology")
            topology = consent_topologies[topology_id]
            topology_server_keys = set(topology.get("server_tag_keys", []))
            topology_flows = [
                flow
                for flow in event_flows
                if topology_server_keys & set(flow.get("server_consumer_keys", []))
            ]
            topology_requirement_ids = {flow["requirement_id"] for flow in topology_flows}
            topology_events = {flow["transported_event"] for flow in topology_flows}
            if not topology_requirement_ids <= set(topology["requirement_ids"]):
                raise ContractValidationError(
                    f"{path} consent topology {topology_id!r} misses destination requirements"
                )
            if not topology_events <= set(topology["event_coverage"]):
                raise ContractValidationError(
                    f"{path} consent topology {topology_id!r} is missing transported event coverage"
                )
            if any(
                objects[key]["target_id"] not in senders
                for key in topology.get("transporter_tag_keys", [])
            ):
                raise ContractValidationError(
                    f"{path} consent topology {topology_id!r} binds a non-sender transporter"
                )
            transporter_keys = set(topology.get("transporter_tag_keys", []))
            for key in transporter_keys:
                operation = objects[key]
                if key == transport_owner:
                    continue
                direct_endpoint = web_support._configured_transport_endpoint(
                    operation, objects, f"{path}.transporter_tag_keys[{key!r}]"
                )
                destinations = web_support._configured_destinations(
                    operation["intended"], objects, f"{path}.transporter_tag_keys[{key!r}]"
                )
                if direct_endpoint != resolved_endpoint and not (
                    destinations and destinations & owner_destinations
                ):
                    raise ContractValidationError(
                        f"{path} consent topology {topology_id!r} transporter {key!r} "
                        "does not inherit the proved endpoint"
                    )
            if not topology_server_keys <= all_server_consumers:
                raise ContractValidationError(
                    f"{path} consent topology {topology_id!r} binds a tag outside its event flows"
                )
            bound_server_consumers.update(topology_server_keys)
            if topology.get("signal_authority") == "third-party-cmp":
                signal_path = topology.get("server_signal_path")
                consent_fields = [
                    field
                    for field in field_flows
                    if field.get("status") == "proved"
                    and field.get("event_data", {}).get("path") == signal_path
                ]
                covered = {
                    requirement_id
                    for field in consent_fields
                    for requirement_id in field.get("requirement_ids", [])
                }
                if not topology_requirement_ids <= covered:
                    raise ContractValidationError(
                        f"{path} third-party CMP signal is not proved on every destination flow"
                    )
        if bound_server_consumers != all_server_consumers:
            raise ContractValidationError(
                f"{path} consent topology bindings differ from server consumers"
            )
        linked_dedup_ids = _unique_texts(
            pipeline.get("dedup_contract_ids"), f"{path}.dedup_contract_ids"
        )
        for dedup_id in linked_dedup_ids:
            if dedup_id not in dedup_contracts:
                raise ContractValidationError(f"{path} references unknown dedup contract")
            dedup = dedup_contracts[dedup_id]
            matching_flows = [
                flow
                for flow in event_flows
                if flow["requirement_id"] == dedup["requirement_id"]
                and dedup["event_name"] in {flow["source_event"], flow["transported_event"]}
            ]
            if not matching_flows:
                raise ContractValidationError(
                    f"{path} dedup contract {dedup_id!r} is detached from its event flow"
                )
            if dedup.get("strategy") == "dual-shared-id":
                variable_key = dedup["source_variable_key"]
                variable = objects.get(variable_key)
                if (
                    variable is None
                    or variable.get("resource_family") != "variable"
                    or variable.get("target_id") not in senders
                ):
                    raise ContractValidationError(
                        f"{path} dedup contract {dedup_id!r} needs a sender web variable"
                    )
                reference_name = _reference_name(dedup["source_reference"])
                if reference_name is not None and variable.get("name") != reference_name:
                    raise ContractValidationError(
                        f"{path} dedup source reference differs from its variable object"
                    )
                browser_keys = set(dedup["browser_consumer_keys"])
                transporter_keys = set(dedup["transporter_consumer_keys"])
                if browser_keys & transporter_keys:
                    raise ContractValidationError(
                        f"{path} browser and transporter dedup consumers must be distinct"
                    )
                for role, keys in (
                    ("browser", browser_keys),
                    ("transporter", transporter_keys),
                ):
                    for key in keys:
                        consumer = objects.get(key)
                        if (
                            consumer is None
                            or not _active_tag(consumer)
                            or consumer.get("target_id") not in senders
                        ):
                            raise ContractValidationError(
                                f"{path} {role} dedup consumers must reference active sender tags"
                            )
                        if dedup["requirement_id"] not in consumer.get("requirement_ids", []):
                            raise ContractValidationError(
                                f"{path} {role} dedup consumer lacks the dedup requirement"
                            )
                        if dedup["source_reference"] not in _reference_values(
                            consumer.get("intended", {})
                        ):
                            raise ContractValidationError(
                                f"{path} {role} dedup consumer does not use the shared ID"
                            )
                for key in transporter_keys:
                    if transport_owner not in objects[key].get("depends_on", []):
                        raise ContractValidationError(
                            f"{path} transporter dedup consumer must depend on transport owner"
                        )
        dependencies = _unique_texts(
            pipeline.get("operation_dependencies", []), f"{path}.operation_dependencies"
        )
        if any(value not in objects for value in dependencies):
            raise ContractValidationError(
                f"{path}.operation_dependencies references unknown objects"
            )
        required_keys = {client_key}
        for flow in event_flows:
            required_keys.update(flow.get("server_consumer_keys", []))
        for field in field_flows:
            if field.get("status") == "proved":
                required_keys.add(field["receiver_owner"])
                if field.get("transformation_owner"):
                    required_keys.add(field["transformation_owner"])
        for topology_id in topology_links:
            blocking_key = (
                consent_topologies[topology_id]
                .get("server_enforcement", {})
                .get("blocking_trigger_key")
            )
            if blocking_key:
                required_keys.add(blocking_key)
        missing_dependencies = sorted(required_keys - set(dependencies))
        if missing_dependencies:
            raise ContractValidationError(
                f"{path}.operation_dependencies misses receiver objects: "
                + ", ".join(missing_dependencies)
            )
        cutover = _text(pipeline.get("cutover_operation_key"), f"{path}.cutover_operation_key")
        if cutover != transport_owner:
            raise ContractValidationError(
                f"{path}.cutover_operation_key must be the pipeline transport owner"
            )
        if objects[cutover].get("risk") != "high-impact":
            raise ContractValidationError(f"{path}.cutover_operation_key must be high-impact")
        missing_cutover_dependencies = sorted(
            required_keys - set(objects[cutover].get("depends_on", []))
        )
        if missing_cutover_dependencies:
            raise ContractValidationError(
                f"{path} cutover does not depend directly on every receiver prerequisite: "
                + ", ".join(missing_cutover_dependencies)
            )
    for (target_id, request_class), clients in receiver_claims.items():
        if len(clients) != 1:
            raise ContractValidationError(
                f"server target {target_id!r} request class {request_class!r} has "
                f"{len(clients)} intended claiming Clients"
            )
    linked_dedup = {
        value for pipeline in pipelines for value in pipeline.get("dedup_contract_ids", [])
    }
    unlinked_dedup = sorted(set(dedup_contracts) - linked_dedup)
    if unlinked_dedup:
        raise ContractValidationError(
            "dedup contracts must be linked to a pipeline: " + ", ".join(unlinked_dedup)
        )


def _validate_evidence(raw: Any, requirement_ids: set[str]) -> None:
    grades: set[str] = set()
    officially_supported: set[str] = set()
    for index, value in enumerate(_array(raw, "$.evidence")):
        path = f"$.evidence[{index}]"
        evidence = _object(value, path)
        grade = _text(evidence.get("grade"), f"{path}.grade")
        if grade not in EVIDENCE_GRADES:
            raise ContractValidationError(f"{path}.grade is unsupported")
        grades.add(grade)
        locator = _text(evidence.get("locator"), f"{path}.locator")
        if grade == "official-current":
            for field in ("title", "decision"):
                _text(evidence.get(field), f"{path}.{field}")
            try:
                parsed = urlparse(locator)
                valid_locator = (
                    parsed.scheme == "https"
                    and bool(parsed.hostname)
                    and parsed.username is None
                    and parsed.password is None
                )
            except ValueError:
                valid_locator = False
            if not valid_locator:
                raise ContractValidationError(
                    f"{path}.locator must be a credential-free HTTPS documentation URL"
                )
            try:
                accessed_on = date.fromisoformat(
                    _text(evidence.get("accessed_on"), f"{path}.accessed_on")
                )
            except ValueError as exc:
                raise ContractValidationError(f"{path}.accessed_on must be an ISO date") from exc
            age = (date.today() - accessed_on).days
            if age < 0:
                raise ContractValidationError(f"{path}.accessed_on cannot be in the future")
            if age > _MAX_OFFICIAL_EVIDENCE_AGE_DAYS:
                raise ContractValidationError(
                    f"{path}.official-current evidence is older than "
                    f"{_MAX_OFFICIAL_EVIDENCE_AGE_DAYS} days"
                )
            supports = set(
                _unique_texts(evidence.get("supports"), f"{path}.supports", allow_empty=False)
            )
            if supports - requirement_ids:
                raise ContractValidationError(f"{path}.supports contains an unknown requirement")
            officially_supported.update(supports)
    if not {"official-current", "container-confirmed"} <= grades:
        raise ContractValidationError(
            "$.evidence needs official-current and container-confirmed records"
        )
    if officially_supported != requirement_ids:
        raise ContractValidationError(
            "official-current evidence must support every included requirement; missing="
            + repr(sorted(requirement_ids - officially_supported))
        )


def validate_document(value: Any) -> dict[str, Any]:
    contract = _object(value, "$")
    version = contract.get("schema_version")
    if version is None:
        raise ContractValidationError(
            "$.schema_version is required; unversioned inputs cannot authorize mutation"
        )
    if version != SCHEMA_VERSION:
        raise ContractValidationError(f"$.schema_version must be {SCHEMA_VERSION!r}")
    unexpected = sorted(set(contract) - TOP_LEVEL_KEYS)
    missing = sorted(TOP_LEVEL_KEYS - set(contract))
    if unexpected:
        raise ContractValidationError(f"unexpected top-level key(s): {', '.join(unexpected)}")
    if missing:
        raise ContractValidationError(f"missing top-level key(s): {', '.join(missing)}")
    leaks = sensitive_paths(contract)
    if leaks:
        raise ContractValidationError(
            "contract contains literal secret or user data at: " + ", ".join(leaks)
        )
    mode = _text(contract["mode"], "$.mode")
    if mode not in RUN_MODES:
        raise ContractValidationError(f"$.mode has unsupported value {mode!r}")
    route = _text(contract["route"], "$.route")
    if route not in ROUTES:
        raise ContractValidationError(f"$.route has unsupported value {route!r}")
    requirement_ids = _validate_scope_and_requirements(contract, route)
    targets = _validate_targets(contract["targets"], mode)
    implementation = _object(contract["implementation"], "$.implementation")
    if not {"execution_mode", "objects"} <= set(implementation) or set(implementation) - {
        "execution_mode",
        "objects",
        "field_bindings",
    }:
        raise ContractValidationError(
            "$.implementation requires execution_mode and objects, with optional field_bindings"
        )
    execution_mode = _text(implementation["execution_mode"], "$.implementation.execution_mode")
    requirement_by_id = {item["id"]: item for item in contract["requirements"]}
    objects, _ = _validate_objects(implementation["objects"], targets, requirement_by_id)
    implemented_requirement_ids = {
        requirement_id
        for item in objects.values()
        for requirement_id in item.get("requirement_ids", [])
    }
    missing_implementation = sorted(requirement_ids - implemented_requirement_ids)
    if missing_implementation:
        raise ContractValidationError(
            "every included requirement needs an implementing create/update/reuse/untouched "
            f"object; missing={missing_implementation}"
        )
    consent_topologies = _validate_consent_topologies(
        contract["consent_topologies"], requirement_ids, objects, targets, mode
    )
    dedup_contracts = _validate_dedup_contracts(contract["dedup_contracts"], requirement_ids)
    _validate_pipelines(
        contract["pipelines"],
        mode,
        targets,
        objects,
        requirement_ids,
        requirement_by_id,
        consent_topologies,
        dedup_contracts,
    )
    _validate_server_object_graph(
        objects,
        targets,
        requirement_by_id,
        contract["pipelines"],
    )
    from web_domain_validation import materialize_payload_mappings

    try:
        payload_mappings = materialize_payload_mappings(contract)
    except web_support.RunValidationError as exc:
        raise ContractValidationError(str(exc)) from exc
    for index, pipeline in enumerate(contract["pipelines"]):
        flow_requirement_ids = {flow["requirement_id"] for flow in pipeline.get("event_flows", [])}
        field_flow_identities = {
            (requirement_id, field["field_scope"], field["destination_field"])
            for field in pipeline.get("field_flows", [])
            for requirement_id in field.get("requirement_ids", [])
        }
        mapped_identities = {
            (
                mapping["requirement_id"],
                mapping["field_scope"],
                mapping["destination_field"],
            )
            for mapping in payload_mappings
            if mapping.get("status") == "mapped"
            and mapping.get("requirement_id") in flow_requirement_ids
        }
        missing_field_flows = sorted(mapped_identities - field_flow_identities)
        if missing_field_flows:
            raise ContractValidationError(
                f"$.pipelines[{index}].field_flows misses mapped fields: {missing_field_flows}"
            )
    validate_web_domain(
        execution_mode=execution_mode,
        requirements=[
            {**item, "kind": item.get("kind", route)} for item in contract["requirements"]
        ],
        operations=list(objects.values()),
        target_types={key: item["container_type"] for key, item in targets.items()},
        payload_mappings=payload_mappings,
        consent_topologies=contract["consent_topologies"],
        execution_topologies=contract["execution_topologies"],
        page_view_decisions=contract["page_view_decisions"],
        first_party_data_routes=contract["first_party_data_routes"],
        pipelines=contract["pipelines"],
        inventory_dispositions=contract["inventory_dispositions"],
        external_dependencies=contract["external_dependencies"],
        fail=_fail,
        contract_phase=True,
    )
    _validate_evidence(contract["evidence"], requirement_ids)
    _array(contract["external_dependencies"], "$.external_dependencies")
    return contract


def load_contract(path: Path) -> dict[str, Any]:
    try:
        value = load_json(path)
    except StrictJsonError as exc:
        raise ContractValidationError(str(exc), error_code=exc.error_code) from exc
    return validate_document(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    args = parser.parse_args()
    try:
        contract = load_contract(args.contract)
    except ContractValidationError as exc:
        print(json.dumps({"pass": False, "error_code": exc.error_code, "error": str(exc)}))
        return 2
    print(json.dumps({"pass": True, "schema_version": contract["schema_version"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
