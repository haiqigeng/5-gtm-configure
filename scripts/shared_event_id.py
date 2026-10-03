"""Static gates for one reviewed template-generated ID shared by direct event consumers."""

from __future__ import annotations

from native_configuration import effective_fields, field_key, local_fields, variable_name
from public_identifiers import _locate


def _identity_binding(target, path, expected_field, variables=None):
    """Resolve direct/native Parameter/event-table identity cells, never metadata."""
    if not isinstance(path, list) or not path:
        raise ValueError("missing native identity field path")
    if len(path) == 1:
        field = path[0]
    elif len(path) == 3 and path[0] == "parameter" and path[-1] == "value":
        row, _ = _locate(target, path[:-1])
        field = row.get("key")
    elif (
        len(path) == 7
        and path[:3] == ["parameter", "eventSettingsTable", "list"]
        and path[4:] == ["map", "parameterValue", "value"]
    ):
        field, _ = _locate(target, path[:4] + ["map", "parameter", "value"])
    else:
        raise ValueError("unsupported native identity field path")

    def token(value):
        return "".join(c for c in str(value).casefold() if c.isalnum())

    if token(field) in {"notes", "name", "type"} or token(field) != token(expected_field):
        raise ValueError("native identity path binds a different field")
    effective = effective_fields(target, variables or {})[field_key(expected_field)]
    if len(path) == 1:
        return effective
    value = _locate(target, path)[0]
    if value != effective:
        raise ValueError("native identity cell differs from effective field")
    return value


def validate_sender_dedup(contracts, operations, dependencies, fail):
    """Bind sender-only identity preparation to an explicitly external receiver."""
    if not isinstance(dependencies, list):
        fail("$.external_dependencies must be an array")
        return
    for index, item in enumerate(dependencies):
        if not isinstance(item, dict):
            fail(f"$.external_dependencies[{index}] must be an object")
            return
    by_key = {item.get("object_key"): item for item in operations}
    external = {item.get("id"): item for item in dependencies}
    for contract in contracts:
        dependency = external.get(contract.get("external_receiver_dependency_id"), {})
        if contract.get("requirement_id") not in dependency.get("requirement_ids", []):
            fail("sender dedup requires a requirement-scoped external receiver dependency")
        if contract.get("strategy") != "dual-shared-id":
            fail("sender dedup requires dual-shared-id")
        source = by_key.get(contract.get("source_variable_key"), {})
        if (
            source.get("resource_family") != "variable"
            or source.get("action") in {"remove", "pause"}
            or contract.get("source_reference") != "{{" + str(source.get("name", "")) + "}}"
        ):
            fail("sender dedup source must bind its actual variable")
        browser = set(contract.get("browser_consumer_keys", []))
        transporter = set(contract.get("transporter_consumer_keys", []))
        if not browser or not transporter or browser & transporter:
            fail("sender dedup browser and transporter consumers must be distinct")
        for key in browser | transporter:
            consumer = by_key.get(key, {})
            if (
                consumer.get("target_id") != source.get("target_id")
                or consumer.get("resource_family") != "tag"
                or consumer.get("action") in {"remove", "pause"}
                or consumer.get("intended", {}).get("paused") is True
                or contract.get("requirement_id") not in consumer.get("requirement_ids", [])
            ):
                fail("sender dedup needs active same-target consumers of the shared source")
        _validate_consumers(contract, by_key, fail)


def _validate_consumers(contract, by_key, fail):
    browser = set(contract.get("browser_consumer_keys", []))
    transporter = set(contract.get("transporter_consumer_keys", []))
    source = by_key.get(contract.get("source_variable_key"), {})
    if contract.get("source_reference") != "{{" + str(source.get("name", "")) + "}}":
        fail("dedup source reference must bind its actual variable")
    variables = _variables(by_key, source.get("target_id"))
    bindings = (
        contract.get("generation", {}).get("consumer_bindings")
        if contract.get("source_type") == "generated-event-id"
        else contract.get("consumer_bindings")
    )
    if (
        not isinstance(bindings, list)
        or len(bindings) != len(browser | transporter)
        or {b.get("object_key") for b in bindings if isinstance(b, dict)} != browser | transporter
    ):
        fail("dedup requires exact native consumer_bindings")
        return
    for binding in bindings:
        key = binding["object_key"]
        try:
            value = _identity_binding(
                by_key[key].get("intended", {}),
                binding.get("field_path"),
                contract.get("browser_field")
                if key in browser
                else contract.get("transported_parameter"),
                variables,
            )
        except (KeyError, IndexError, TypeError, ValueError):
            fail(
                "dedup native identity binding does not resolve uniquely; consumer does not use the shared ID"
            )
            continue
        if value != contract.get("source_reference"):
            fail("dedup native identity field does not use its shared source")


def _variables(by_key, target_id):
    return {
        item.get("name"): item.get("intended", {})
        for item in by_key.values()
        if item.get("target_id") == target_id
        and item.get("resource_family") == "variable"
        and item.get("action") not in {"remove", "pause"}
    }


def validate_pipeline_dedup(contracts, operations, pipelines, fail):
    """Bind both sender ID fields and the receiver's Event Data variable."""
    by_key = {item.get("object_key"): item for item in operations}
    for contract in contracts:
        if contract.get("strategy") != "dual-shared-id":
            continue
        _validate_consumers(contract, by_key, fail)
        for pipeline in pipelines:
            if contract.get("dedup_contract_id") not in pipeline.get("dedup_contract_ids", []):
                continue
            receivers = {
                field.get("receiver_owner")
                for field in pipeline.get("field_flows", [])
                if field.get("status") == "proved"
                and contract.get("requirement_id") in field.get("requirement_ids", [])
                and field.get("destination_field") == contract.get("server_field")
                and field.get("event_data", {}).get("path")
                == contract.get("server_event_data_path")
            }
            flow_receivers = {
                key
                for flow in pipeline.get("event_flows", [])
                if flow.get("requirement_id") == contract.get("requirement_id")
                and contract.get("event_name")
                in {flow.get("source_event"), flow.get("transported_event")}
                for key in flow.get("server_consumer_keys", [])
            }
            if not receivers or not receivers <= flow_receivers:
                fail("dedup needs proved receiver identity field ownership in its event flow")
                continue
            for key in receivers:
                consumer = by_key.get(key, {})
                variables = _variables(by_key, consumer.get("target_id"))
                try:
                    reference = _identity_binding(
                        consumer.get("intended", {}),
                        [contract.get("server_field")],
                        contract.get("server_field"),
                        variables,
                    )
                    if (
                        not isinstance(reference, str)
                        or not reference.startswith("{{")
                        or not reference.endswith("}}")
                    ):
                        raise ValueError("receiver needs an Event Data reference")
                    variable = variables[variable_name(reference)]
                    fields = local_fields(variable)
                    if variable.get("type") != "ed" or fields.get("keypath") != contract.get(
                        "server_event_data_path"
                    ):
                        raise ValueError("receiver must read exact transported Event Data")
                except (KeyError, IndexError, TypeError, ValueError):
                    fail(
                        "dedup receiver native identity must read the transported Event Data; no regeneration"
                    )


def validate_generated_event_ids(
    contracts, operations, topologies, target_types, fail, baselines=()
):
    """Use the same checks on source contracts and materialized runs.

    Template behavior/permissions remain an evidence review, not executable proof.
    Saved graph verification binds that review to the inspected template and variable.
    """
    by_key = {item.get("object_key"): item for item in operations}
    by_topology = {item.get("tag_object_key"): item for item in topologies}
    for contract in contracts:
        generated = contract.get("source_type") == "generated-event-id"
        generation = contract.get("generation")
        if not generated:
            if generation is not None:
                fail("dedup generation requires source_type generated-event-id")
            continue
        label = f"dedup {contract.get('dedup_contract_id')!r} generation"
        if contract.get("strategy") != "dual-shared-id":
            fail(f"{label} requires dual-shared-id")
        if str(contract.get("event_name", "")).casefold() == "purchase":
            fail(f"{label} cannot replace a stable purchase/order identifier")
        if not isinstance(generation, dict):
            fail(f"{label} requires the inspected template and consumer field bindings")
            continue
        for field in ("template_object_key", "template_type", "review_locator"):
            if not isinstance(generation.get(field), str) or not generation[field].strip():
                fail(f"{label}.{field} must identify inspected evidence")
        variable = by_key.get(contract.get("source_variable_key"), {})
        target_id = variable.get("target_id")
        template = by_key.get(generation.get("template_object_key"), {})
        template_type = generation.get("template_type", "")
        if (
            target_types.get(target_id) != "web"
            or variable.get("resource_family") != "variable"
            or variable.get("action") in {"remove", "pause"}
            or not isinstance(template_type, str)
            or not template_type.startswith("cvt_")
            or variable.get("intended", {}).get("type") != template_type
        ):
            fail(f"{label} requires the exact reviewed web variable template type")
        if (
            template.get("resource_family") != "template"
            or template.get("target_id") != target_id
            or template.get("action") not in {"reuse", "untouched"}
            or not template.get("object_id")
            or not template.get("intended", {}).get("templateData")
        ):
            fail(f"{label} needs a readback-verifiable installed template with reviewed code")
        dependency = template.get("operation_id", template.get("object_key"))
        if not dependency or dependency not in variable.get(
            "dependencies", variable.get("depends_on", [])
        ):
            fail(f"{label} variable must depend on its inspected template")

        consumers = set(contract.get("browser_consumer_keys", [])) | set(
            contract.get("transporter_consumer_keys", [])
        )
        bindings = generation.get("consumer_bindings")
        if not isinstance(bindings, list) or not bindings:
            fail(f"{label} requires exact native consumer_bindings")
            continue
        bound = set()
        for binding in bindings:
            if not isinstance(binding, dict):
                fail(f"{label} consumer binding must be an object")
                continue
            key, path = binding.get("object_key"), binding.get("field_path")
            if not isinstance(key, str) or key in bound:
                fail(f"{label} needs one binding per consumer")
                continue
            bound.add(key)
            if (
                not isinstance(path, list)
                or not path
                or any(type(part) not in (str, int) for part in path)
                or any(type(part) is int and part < 0 for part in path)
            ):
                fail(f"{label} requires a native field_path array")
                continue
            try:
                value = _identity_binding(
                    by_key.get(key, {}).get("intended", {}),
                    path,
                    contract.get("browser_field")
                    if key in contract.get("browser_consumer_keys", [])
                    else contract.get("transported_parameter"),
                    _variables(by_key, target_id),
                )
            except (KeyError, IndexError, TypeError, ValueError):
                fail(f"{label} consumer field does not resolve uniquely")
                continue
            if value != contract.get("source_reference"):
                fail(f"{label} consumer field does not use the shared variable")
        if bound != consumers:
            fail(f"{label} bindings must cover exactly the browser and transporter consumers")

        trigger_sets = []
        consumer_aliases = set(consumers)
        planned_tag_names = {
            item.get("name")
            for item in operations
            if item.get("target_id") == target_id and item.get("resource_family") == "tag"
        }
        baseline_tags = [
            tag
            for baseline in baselines
            if baseline.get("target_id") == target_id
            for tag in baseline.get("resources", {}).get("tag", [])
        ]
        for key in consumers:
            consumer = by_key.get(key, {})
            intended = consumer.get("intended", {})
            consumer_aliases.update(
                str(value)
                for value in (consumer.get("name"), intended.get("tagId"))
                if value is not None
            )
            consumer_aliases.add("tag::" + str(consumer.get("name", "")))
            consumer_aliases.update(
                str(tag["tagId"])
                for tag in baseline_tags
                if tag.get("name") == consumer.get("name") and tag.get("tagId") is not None
            )
            variable_dependency = variable.get("operation_id", variable.get("object_key"))
            if variable_dependency not in consumer.get(
                "dependencies", consumer.get("depends_on", [])
            ):
                fail(f"{label} every consumer must depend on the shared variable")
            topology = by_topology.get(key, {})
            if (
                consumer.get("target_id") != target_id
                or consumer.get("resource_family") != "tag"
                or topology.get("lifecycle_role") != "event-driven"
                or topology.get("firing_option") != "once-per-event"
            ):
                fail(f"{label} consumers must fire once on the same web-container event")
            triggers = topology.get("normal_triggers", [])
            if not triggers or any(item.get("role") != "source-event" for item in triggers):
                fail(f"{label} requires direct source-event triggers without consent replay")
            trigger_sets.append({item.get("trigger_object_key") for item in triggers})
            if intended.get("setupTag") or intended.get("teardownTag"):
                fail(f"{label} does not support tag sequencing; materialize an ID upstream")
        if not trigger_sets or any(triggers != trigger_sets[0] for triggers in trigger_sets):
            fail(f"{label} consumers must share the exact source-event triggers")
        # Also reject a consumer used as another tag's setup/cleanup tag.
        intended_tags = [
            item.get("intended", {})
            for item in operations
            if item.get("target_id") == target_id and item.get("action") not in {"remove", "pause"}
        ]
        intended_tags.extend(
            tag for tag in baseline_tags if tag.get("name") not in planned_tag_names
        )
        for intended in intended_tags:
            for field in ("setupTag", "teardownTag"):
                for item in intended.get(field, []):
                    if isinstance(item, dict) and str(item.get("tagName")) in consumer_aliases:
                        fail(f"{label} consumer is sequenced by another tag")
