"""Consolidate proven compatible native GA4 event fields during compact preparation."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy

from gtm_configure.core.validation import canonical_sha256
from gtm_configure.domain.events import trigger_accepts_event
from gtm_configure.domain.native import (
    decode_parameter,
    direct_dlv_source,
    variable_name,
    variable_references,
)
from gtm_configure.domain.resources import semantic_object_key
from gtm_configure.domain.web_native import configured_destinations, tag_firing_option


def _event_rows(native):
    tables = [row for row in native.get("parameter", []) if row.get("key") == "eventSettingsTable"]
    if len(tables) != 1 or str(tables[0].get("type", "")).lower() != "list":
        return None
    rows = {}
    for row in tables[0].get("list", []):
        if str(row.get("type", "")).lower() != "map" or len(row.get("map", [])) != 2:
            return None
        decoded = decode_parameter(row)
        if not isinstance(decoded, dict) or set(decoded) != {"parameter", "parameterValue"}:
            return None
        name = decoded["parameter"]
        if not isinstance(name, str) or name in rows:
            return None
        rows[name] = (row, decoded["parameterValue"])
    return tables[0], rows


def _approved_field(contract, tag, name, value, variables):
    """An approved scalar and a native source prove the shared field contract."""
    if name in {"user_data", "user_id", "items"}:
        return None
    signatures = []
    bindings = contract.get(
        "field_bindings", contract.get("implementation", {}).get("field_bindings", [])
    )
    requirements = {item["id"]: item for item in contract["requirements"]}
    for requirement_id in tag["requirement_ids"]:
        requirement = requirements[requirement_id]
        field = requirement.get("parameters", {}).get(name)
        if not isinstance(field, dict):
            return None
        if any(
            route.get("requirement_id") == requirement_id and route.get("destination_field") == name
            for route in contract.get("first_party_data_routes", [])
        ):
            return None
        binding = next(
            (
                item
                for item in bindings
                if item.get("requirement_id") == requirement_id
                and item.get("field_scope") == "event-parameter"
                and item.get("destination_field") == name
            ),
            {},
        )
        if binding and (
            binding.get("status") != "mapped"
            or binding.get("owner_object_key") != tag["object_key"]
        ):
            return None
        if binding.get("gtm_resolution", value) != value:
            return None
        shape = field.get("source_shape")
        if (
            not isinstance(shape, str)
            or not shape.startswith("scalar:")
            or shape != field.get("destination_shape")
        ):
            return None
        if "source" in field:
            if not isinstance(value, str) or not value.startswith("{{") or not value.endswith("}}"):
                return None
            variable = variables.get(variable_name(value))
            if variable is None:
                return None
            try:
                if direct_dlv_source(variable) != field["source"]:
                    return None
            except ValueError:
                return None
        elif "literal" in field:
            if canonical_sha256(field["literal"]) != canonical_sha256(value):
                return None
        else:
            return None
        semantics = {
            key: child
            for key, child in field.items()
            if key not in {"provenance", "source_authority"}
        }
        semantics["missing_behavior"] = binding.get(
            "missing_behavior", field.get("missing_behavior")
        )
        if not semantics["missing_behavior"]:
            return None
        signatures.append(canonical_sha256(semantics))
    return signatures[0] if signatures and len(set(signatures)) == 1 else None


def consolidate_event_settings(contract: dict, objects: list[dict]) -> list[dict]:
    """Move common compatible local fields to one native Event Settings owner.

    Only create/update consumers with ordinary source-event lifetimes participate.
    Existing inheritance and local overrides retain their exact current owners.
    The caller runs reference closure and derives approvals after this transformation.
    """
    indexed = {
        item["object_key"]: {**item, "object_type": item["resource_family"]} for item in objects
    }
    requirements = {item["id"]: item for item in contract["requirements"]}
    policies = {item["tag_object_key"]: item for item in contract.get("tag_policies", [])}
    consent_ids = {item["consent_policy_id"] for item in contract.get("consent_policies", [])}
    groups = defaultdict(list)
    for tag in objects:
        native = tag.get("intended", {})
        if (
            tag["resource_family"] != "tag"
            or tag["action"] not in {"create", "update"}
            or native.get("type") != "gaawe"
            or native.get("paused") is True
        ):
            continue
        if any(
            row.get("key") in {"eventSettingsVariable", "inheritedEventSettings"}
            for row in native.get("parameter", [])
        ) or any(key in native for key in {"eventSettingsVariable", "inheritedEventSettings"}):
            continue
        policy = policies.get(tag["object_key"], {})
        if (
            policy.get("lifecycle_role") != "event-driven"
            or policy.get("consent_policy_id") not in consent_ids
        ):
            continue
        triggers = native.get("firingTriggerId", [])
        if not triggers or any(
            indexed.get(key, {}).get("intended", {}).get("type") != "customEvent"
            for key in triggers
        ):
            continue
        if any(
            not all(
                trigger_accepts_event(
                    indexed[key]["intended"], requirements[rid].get("source_event", "")
                )
                for key in triggers
            )
            for rid in tag["requirement_ids"]
        ):
            continue
        parsed = _event_rows(native)
        if parsed is None:
            continue
        variables = {
            item["name"]: item.get("intended") or item.get("pre_change") or {}
            for item in objects
            if item["resource_family"] == "variable"
            and item["target_id"] == tag["target_id"]
            and item["action"] not in {"remove", "pause"}
        }
        try:
            destinations = sorted(
                configured_destinations(native, indexed, "shared settings consumer")
            )
            if not destinations:
                continue
        except ValueError:
            continue
        table, rows = parsed
        candidates = {
            name: (row, value, signature)
            for name, (row, value) in rows.items()
            if (signature := _approved_field(contract, tag, name, value, variables)) is not None
        }
        if not candidates:
            continue
        signature = canonical_sha256(
            {
                "target": tag["target_id"],
                "destinations": destinations,
                "consent_policy": policy["consent_policy_id"],
                "lifecycle": policy["lifecycle_role"],
                "pre_cmp_policy": policy.get("pre_cmp_policy"),
                "firing_option": tag_firing_option(native, "shared settings consumer"),
                "blocks": sorted(native.get("blockingTriggerId", [])),
                "consent_settings": native.get("consentSettings"),
            }
        )
        groups[signature].append((tag, table, candidates))
    added = []
    for signature, consumers in sorted(groups.items()):
        if len(consumers) < 2:
            continue
        common = set.intersection(*(set(fields) for _, _, fields in consumers))
        common = {
            name
            for name in common
            if len(
                {
                    canonical_sha256(
                        {"row": decode_parameter(fields[name][0]), "semantics": fields[name][2]}
                    )
                    for _, _, fields in consumers
                }
            )
            == 1
        }
        if not common:
            continue
        rows = [deepcopy(consumers[0][2][name][0]) for name in sorted(common)]
        tag_keys = sorted(tag["object_key"] for tag, _, _ in consumers)
        digest = canonical_sha256(
            {"group": signature, "consumers": tag_keys, "fields": rows}
        ).split(":", 1)[1][:12]
        name = "Google Event Settings - shared " + digest
        target_id = consumers[0][0]["target_id"]
        key = semantic_object_key(target_id, "variable", name)
        if key in indexed:
            raise ValueError("Generated shared-settings identity conflicts with an authored object")
        references = variable_references(rows)
        dependencies = sorted(
            item["object_key"]
            for item in objects
            if item["resource_family"] == "variable"
            and item["target_id"] == target_id
            and item["name"] in references
        )
        operation = {
            "target_id": target_id,
            "resource_family": "variable",
            "name": name,
            "object_key": key,
            "action": "create",
            "requirement_ids": sorted(
                {rid for tag, _, _ in consumers for rid in tag["requirement_ids"]}
            ),
            "depends_on": dependencies,
            "justification": "One native owner for approved identical scalar event fields across compatible consumers",
            "evidence": ["approved-input", "official-current"],
            "risk": "routine",
            "intended": {
                "type": "gtes",
                "parameter": [{"type": "list", "key": "eventSettingsTable", "list": rows}],
            },
        }
        for tag, table, fields in consumers:
            table["list"] = [
                row for row in table["list"] if row not in [fields[field][0] for field in common]
            ]
            if not table["list"]:
                tag["intended"]["parameter"].remove(table)
            tag["intended"]["parameter"].append(
                {"type": "template", "key": "eventSettingsVariable", "value": "{{" + name + "}}"}
            )
            tag["depends_on"] = sorted(set(tag["depends_on"]) | {key})
        objects.append(operation)
        added.append(operation)
    return added
