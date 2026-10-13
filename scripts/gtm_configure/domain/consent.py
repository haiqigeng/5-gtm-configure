"""Static proof for explicitly selected existing web consent conventions."""

from typing import Any, Callable

from gtm_configure.core.public_identifiers import locate
from gtm_configure.domain.localization import (
    local_array,
)
from gtm_configure.domain.native import (
    decode_parameter,
)
from gtm_configure.domain.web_model import BUILT_IN_TRIGGER_TYPES

ALTERNATIVE_GATES = {"firing-trigger-condition", "additional-consent-checks"}


def validate_convention(execution, enforcement, operations, fail):
    mechanism = enforcement.get("mechanism")
    if mechanism not in ALTERNATIVE_GATES:
        return
    evidence = enforcement.get("evidence")
    if not isinstance(evidence, str) or not evidence.strip():
        fail("Existing consent convention requires inspected container/default/lifecycle evidence")
    if execution.get("blocking_trigger_keys") or execution.get("blocking_event_scope"):
        fail("Alternative consent convention cannot also declare vendor blocking triggers")

    def snapshot(key):
        operation = operations.get(key)
        if operation is None or operation.get("action") in {"remove", "pause"}:
            fail("Consent proof references no active in-scope object")
        return operation.get("intended") or operation.get("pre_change") or {}

    if mechanism == "firing-trigger-condition":
        condition = enforcement.get("grant_condition")
        if not isinstance(condition, dict) or condition.get("type") not in {
            "equals",
            "contains",
        }:
            fail("Firing gate needs an exact positive equals/contains grant_condition")
        entries = condition.get("parameter", [])
        if not isinstance(entries, list) or any(not isinstance(row, dict) for row in entries):
            fail("Invalid grant_condition parameters")
        params = {row.get("key"): decode_parameter(row) for row in entries}
        if len(params) != len(entries) or set(params) != {"arg0", "arg1"}:
            fail("Grant predicate needs exactly arg0 and arg1, without negation or flags")
        source, granted = params["arg0"], params["arg1"]
        if (
            not isinstance(source, str)
            or not source.startswith("{{")
            or not source.endswith("}}")
            or source in {"{{Event}}", "{{_event}}"}
        ):
            fail("Grant predicate must read an inspected consent variable")
        if (
            not isinstance(granted, str)
            or not granted
            or any(
                granted.casefold() in state for state in ("undefined", "null", "false", "denied")
            )
        ):
            fail("Grant predicate must reject missing and denied consent")
        if execution.get("additional_consent_checks"):
            fail("Firing-trigger convention cannot also use Additional Consent Checks")
        for trigger in execution["normal_triggers"]:
            configured = snapshot(trigger["trigger_object_key"])
            if condition not in configured.get("filter", []):
                fail("Every firing trigger must contain the exact positive grant_condition")
    else:
        if (
            execution.get("lifecycle_role") != "event-driven"
            or execution.get("firing_option") != "once-per-event"
        ):
            fail("Additional Consent Checks convention requires event-driven once-per-event tags")
        checks = execution.get("additional_consent_checks", [])
        bindings = enforcement.get("default_bindings")
        if not checks or not isinstance(bindings, dict) or set(bindings) != set(checks):
            fail("Every Additional Consent Check requires an exact denied default binding")
        for binding in bindings.values():
            if not isinstance(binding, dict) or set(binding) != {
                "object_key",
                "field_path",
            }:
                fail("Consent default binding needs object_key and field_path")
            owner = snapshot(binding["object_key"])
            if (
                owner.get("paused") is True
                or owner.get("blockingTriggerId")
                or owner.get("consentSettings", {}).get("consentStatus") == "needed"
            ):
                fail("Consent default owner must run without a consent gate")
            operation = operations[binding["object_key"]]
            if operation.get("resource_family", operation.get("object_type")) != "tag" or not str(
                owner.get("type", "")
            ).startswith("cvt_"):
                fail("Consent default owner must be an inspected CMP template tag")
            by_id = {item.get("operation_id", key): key for key, item in operations.items()}
            pending = [execution["tag_object_key"]]
            closure = set()
            while pending:
                key = pending.pop()
                if key in closure:
                    continue
                closure.add(key)
                item = operations.get(key, {})
                pending.extend(
                    by_id.get(dep, dep)
                    for dep in item.get("depends_on", item.get("dependencies", []))
                )
            if binding["object_key"] not in closure:
                fail("Consent default owner must be an explicit tag dependency")
            if not any(
                (
                    key == builtin.rsplit("::", 1)[-1]
                    or key == builtin
                    or str(key).endswith("::" + builtin)
                )
                and trigger_type == "consent-initialization"
                for key in owner.get("firingTriggerId", [])
                for builtin, trigger_type in BUILT_IN_TRIGGER_TYPES.items()
            ):
                fail("Consent default owner must fire on Consent Initialization")
            path = binding["field_path"]
            if (
                not isinstance(path, list)
                or not path
                or any(type(key) not in {str, int} for key in path)
            ):
                fail("Consent default field_path must be a non-empty native path")
            try:
                value, _ = locate(owner, path)
            except (KeyError, IndexError, TypeError):
                fail("Consent default binding does not resolve")
            if value != "denied":
                fail("Consent default binding must resolve to denied")


def validate_topology_consent_binding(
    source: dict[str, Any],
    *,
    consent_by_id: dict[str, dict[str, Any]],
    path: str,
    fail: Callable[[str], None],
) -> None:
    tag_key = source.get("tag_object_key")
    topology_ids = local_array(
        source.get("consent_topology_ids"), f"{path}.consent_topology_ids", error_type=fail
    )
    if not topology_ids:
        fail(f"{path}.consent_topology_ids must not be empty")
    if len(set(topology_ids)) != len(topology_ids):
        fail(f"{path}.consent_topology_ids contains duplicates")
    linked_requirements = set(source.get("requirement_ids", []))
    for topology_id in topology_ids:
        topology = consent_by_id.get(topology_id)
        if topology is None:
            fail(f"{path} references unknown consent topology {topology_id!r}")
            continue
        if not linked_requirements <= set(topology.get("requirement_ids", [])):
            fail(f"{path} consent topology {topology_id!r} does not cover its requirements")
        if source.get("consent_mode") != topology.get("consent_mode"):
            fail(f"{path}.consent_mode differs from consent topology {topology_id!r}")
        mechanism = topology.get("web_enforcement", {}).get("mechanism")
        is_transporter = tag_key in set(topology.get("transporter_tag_keys", []))
        if source.get("consent_mode") == "strict-basic":
            allowed = (
                {"transport-trigger-only"}
                if is_transporter and topology.get("transporter_destination_vendor_block") is False
                else {
                    "cmp-lifecycle-plus-vendor-block",
                    "business-trigger-plus-vendor-block",
                    *ALTERNATIVE_GATES,
                }
            )
            if mechanism not in allowed:
                fail(f"{path}.strict-basic consent mechanism differs from the tag's route role")
            if mechanism in ALTERNATIVE_GATES and topology.get("unknown_state_behavior") != "deny":
                fail("Alternative strict-basic conventions must fail closed on unknown consent")
        native_google_carrier = (
            is_transporter
            and mechanism == "transport-trigger-only"
            and topology.get("signal_authority") == "google-consent-mode"
            and topology.get("server_enforcement", {}).get("mechanism")
            in {"incoming-google-consent-native", "none"}
        )
        if (
            source.get("consent_mode") == "advanced-native"
            and not native_google_carrier
            and mechanism
            not in {
                "google-consent-mode",
                "product-native",
            }
        ):
            fail(f"{path}.advanced-native needs a documented native consent mechanism")
