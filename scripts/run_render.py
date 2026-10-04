"""Human configuration-result rendering for configuration-run@5.0."""

from __future__ import annotations

import html
import json
import re
import unicodedata
from typing import Any
from urllib.parse import quote, urlsplit

from diff_object_graph import ID_FIELDS, GraphError, normalize_graph
from native_configuration import FieldResolutionError, decode_parameter, supports_native_mapping
from public_identifiers import public_identifier_paths
from redaction import redact_for_persistence, sensitive_findings


def semantic_field_changes(operation: dict, document: dict) -> list[str]:
    """Use the verification canonicalizer for human deltas as well."""
    target = operation["target_id"]
    context = [
        {**item, "target_id": target, "object_type": family}
        for baseline in document["container_baselines"]
        if baseline["target_id"] == target
        for family, items in baseline.get("resources", {}).items()
        for item in items
        if not (family == operation["resource_family"] and item.get("name") == operation["name"])
    ]
    types = {item["target_id"]: item["container_type"] for item in document["run"]["targets"]}
    allowed = {item["object_key"] for item in document["object_changes"]}

    def body(raw: dict, name: str) -> dict:
        if not raw:
            return {}
        graph = {
            "objects": [
                {
                    **raw,
                    "target_id": target,
                    "object_type": operation["resource_family"],
                    "name": name,
                }
            ],
            "context_objects": context,
        }
        normalized = normalize_graph(graph, target_types=types, allowed_semantic_references=allowed)
        return next(iter(normalized.values()))

    try:
        before = body(operation.get("pre_change", {}), operation["name"])
        after = body(
            operation.get("intended", {}) if operation["action"] != "remove" else {},
            operation.get("new_name", operation["name"]),
        )
    except GraphError:
        return [
            "Semantic delta unavailable: reference context is incomplete; inspect the machine comparison"
        ]
    return analyst_field_changes(before, after) or ["No semantic field changes"]


_LABELS = {
    "name": "Name",
    "type": "Tag/variable/trigger type",
    "measurementId": "Measurement ID",
    "measurementIdOverride": "Measurement ID",
    "eventName": "Event name",
    "tagId": "Tag ID",
    "conversionId": "Conversion ID",
    "conversionLabel": "Conversion label",
    "conversionValue": "Conversion value",
    "transactionId": "Transaction ID",
    "currencyCode": "Currency",
    "firingTriggerId": "Fires on",
    "blockingTriggerId": "Blocked by",
    "tagFiringOption": "Firing option",
    "consentSettings": "Consent settings",
    "html": "Custom HTML",
    "paused": "Paused",
    "eventSettingsTable": "Parameters",
    "eventParameters": "Parameters",
    "configSettingsTable": "Configuration parameters",
}


def _analyst_fields(snapshot: dict) -> dict:
    fields = {
        _LABELS.get(key, key): value
        for key, value in snapshot.items()
        if key not in {"object_type", "target_id", "parameter"}
    }
    for row in snapshot.get("parameter", []):
        key = row.get("key", "Unknown parameter")
        value = decode_parameter(row)
        if key in {"eventSettingsTable", "configSettingsTable", "eventParameters"}:
            name, content = (
                ("name", "value") if key == "eventParameters" else ("parameter", "parameterValue")
            )
            # Retain malformed/unrecognized rows rather than silently hiding fields.
            if isinstance(value, list) and all(
                isinstance(item, dict) and set(item) == {name, content} for item in value
            ):
                value = "; ".join(f"{item[name]} = {item[content]}" for item in value)
        label = _LABELS.get(key, key)
        if label in fields:
            label = f"Native parameter {key}"
        fields[label] = value
    return fields


def analyst_field_changes(before: dict, after: dict) -> list[str]:
    """Label native fields without discarding unknown configuration or machine evidence."""
    try:
        before, after = _analyst_fields(before), _analyst_fields(after)
    except (FieldResolutionError, TypeError, AttributeError):
        return field_changes(before, after)

    def display(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return ", ".join(value) or "none"
        return json.dumps(value, ensure_ascii=False)

    return [
        f"{key}: {display(before[key]) if key in before else 'absent'} → {display(after[key]) if key in after else 'absent'}"
        for key in sorted(before.keys() | after.keys())
        if key not in before or key not in after or before[key] != after[key]
    ]


def _at_path(value: Any, path: str) -> Any:
    for key, index in re.findall(r"\.([^.[\]]+)|\[(\d+)\]", path):
        value = value[int(index)] if index else value[key]
    return value


def _workspace_change_summary(items: Any) -> str:
    if not items:
        return "none"
    if not isinstance(items, list):
        return "recorded in machine artifact"
    result = []
    for change in items:
        kind = next((key for key, value in change.items() if isinstance(value, dict)), None)
        obj = change[kind] if kind else change
        result.append(
            f"{change.get('type', change.get('changeStatus', 'changed'))}: {kind or obj.get('object_type', 'object')} / {obj.get('name', 'unnamed')}"
        )
    return "; ".join(result)


def field_changes(before: Any, after: Any, path: str = "$") -> list[str]:
    """Describe only changed fields; ordered lists remain order-sensitive."""
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        changes = []
        for key in sorted(before.keys() | after.keys()):
            location = f"{path}.{key}"
            if key not in before:
                changes.append(f"{location}: absent → {json.dumps(after[key], ensure_ascii=False)}")
            elif key not in after:
                changes.append(
                    f"{location}: {json.dumps(before[key], ensure_ascii=False)} → absent"
                )
            else:
                changes.extend(field_changes(before[key], after[key], location))
        return changes
    # Keyed Parameter arrays are maps; ordinary lists preserve their sequence.
    if isinstance(before, list) and isinstance(after, list):

        def keyed(items):
            return (
                bool(items)
                and all(isinstance(x, dict) and "key" in x for x in items)
                and len({x["key"] for x in items}) == len(items)
            )

        if keyed(before) and keyed(after) and not path.endswith(".list"):
            return field_changes({x["key"]: x for x in before}, {x["key"]: x for x in after}, path)
    return [
        f"{path}: {json.dumps(before, ensure_ascii=False)} → {json.dumps(after, ensure_ascii=False)}"
    ]


def _cell(value: Any) -> str:
    text = str(value if value is not None else "")
    text = "".join(
        " " if unicodedata.category(char) in {"Cc", "Cf", "Zl", "Zp"} else char for char in text
    )
    text = html.escape(text.replace("\\", "\\\\"), quote=False)
    text = re.sub(r"(?<!\w)_|_(?!\w)", r"\\_", text)
    return re.sub(r"([`*[\]{}()#+!|>~])", r"\\\1", text)


def _source_link(source: dict) -> str:
    title, url = _cell(source["title"]), source["url"]
    try:
        parsed = urlsplit(url)
        safe = (
            parsed.scheme in {"https", "http"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        safe = False
    return f"[{title}]({quote(url, safe=':/?=&%#@+;,')})" if safe else title


def _saved_object_id(operation: dict) -> Any:
    saved = operation.get("saved_readback")
    objects = saved.get("objects", []) if isinstance(saved, dict) else saved or []
    for obj in objects:
        if (
            obj.get("target_id") == operation["target_id"]
            and obj.get("object_type") == operation["resource_family"]
            and obj.get("name") == operation.get("new_name", operation["name"])
        ):
            return next(
                (
                    obj.get(field)
                    for field, family in ID_FIELDS.items()
                    if family == operation["resource_family"]
                ),
                None,
            )
    return None


def render_markdown(document: dict[str, Any], *, embed_machine: bool = False) -> str:
    document = redact_for_persistence(
        document, public_identifier_paths=public_identifier_paths(document)
    )
    run = document["run"]
    operations = document["object_changes"]
    counts: dict[str, int] = {}
    for operation in operations:
        counts[operation["action"]] = counts.get(operation["action"], 0) + 1
    preview = run["phase"] == "preflight" and all(
        (operation["state"] == "planned" for operation in operations)
    )
    heading = "Pre-mutation impact preview" if preview else "GTM configuration result"
    lines = [
        f"# {_cell(heading)}",
        "",
        "## Executive summary",
        "",
        f"- Verdict: **{_cell(run['status'])}**",
        f"- Run: {_cell(run['id'])}; mode: {_cell(run['mode'])}; phase: {_cell(run['phase'])}",
        f"- Requirements: {_cell(len(document['requirements']))}",
        f"- Execution mode: {_cell(run['execution_mode'])}",
        "- Intended object actions: "
        + (
            ", ".join((f"{_cell(key)} {_cell(value)}" for key, value in sorted(counts.items())))
            or "none"
        ),
        f"- Consent topologies: {_cell(len(document['consent_topologies']))}",
        f"- Pipelines: {_cell(len(document['pipelines']))}",
        "- Publication: not performed; no GTM version created",
        "- Runtime recette: not performed",
        "",
        "## Targets and baseline",
        "",
        "| Target | Type | Account | Container | Workspace | Baseline complete | Existing changes |",
        "| --- | --- | --- | --- | --- | --- | ---: |",
    ]
    types = {target["target_id"]: target["container_type"] for target in document["run"]["targets"]}
    alerts = []
    for baseline in document["container_baselines"]:
        resources = baseline.get("resources", {})
        for finding in sensitive_findings(
            resources,
            include_redacted=True,
            public_identifier_paths=public_identifier_paths(
                resources,
                records=[item for item in operations if item["target_id"] == baseline["target_id"]],
            ),
        ):
            owner = _at_path(resources, finding["object_path"])
            name = (
                owner.get("name", finding["object_path"])
                if isinstance(owner, dict)
                else finding["object_path"]
            )
            category = finding["category"]
            label = (
                "Credential or public query key — classification required"
                if finding["detector"] == "credential-query"
                else "Credential-like literal"
                if category == "credential"
                else "Personal data"
                if category == "pii"
                else "Redacted sensitive field (classification unconfirmed)"
            )
            action = (
                "Inspect official field documentation; declare an exact public identifier only when supported by that evidence."
                if finding["detector"] == "credential-query"
                else "Review credential custody and rotate if exposure is confirmed."
                if category == "credential"
                else "Review the authorized data source and collection scope."
            )
            alerts.append(
                f"- **{_cell(label)}: {_cell(name)}** in {_cell(baseline['target_id'])} at {_cell(finding['path'])} ({_cell(finding['detector'])}). {_cell(action)} Values are omitted; live publication and host-log exposure are not established by this report."
            )
    for result in document["target_results"]:
        if result.get("baseline_error"):
            alerts.append(
                f"- **Baseline unavailable: {_cell(result['target_id'])}** — {_cell(result['baseline_error']['error'])}. No write was attempted; resume retries the baseline."
            )
    for operation in operations:
        if operation.get("error"):
            alerts.append(
                f"- **{_cell(operation['state'])}: {_cell(operation['name'])}** — {_cell(operation['error'])}"
            )
    alerts.extend(
        (
            f"- External [{_cell(item['status'])}] {_cell(item['owner'])}: {_cell(item['action'])}"
            for item in document["external_dependencies"]
            if item["status"] == "open"
        )
    )
    if alerts:
        position = lines.index("## Targets and baseline")
        lines[position:position] = ["## Findings and required actions", "", *alerts, ""]
    baselines = {item["target_id"]: item for item in document["container_baselines"]}
    for target in run["targets"]:
        baseline = baselines[target["target_id"]]
        lines.append(
            f"| {_cell(target['target_id'])} | {_cell(target['container_type'])} | {_cell(target['account_id'])} | {_cell(target['container_id'])} | {_cell(target['workspace_id'])} | {_cell(baseline['complete'])} | {_cell(_workspace_change_summary(baseline.get('preexisting_workspace_changes')))} |"
        )
    if document["inventory_dispositions"]:
        lines.extend(
            [
                "",
                "## Inventory-aligned tag change log",
                "",
                "| Order | Source row | Vendor/source | Disposition | Tag before | Tag after | Trigger before | Trigger after | Variable changes | Parameter changes | Consent changes | Rationale |",
                "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in sorted(
            document["inventory_dispositions"], key=lambda value: value["source_order"]
        ):
            lines.append(
                "| {order} | {row} | {source} | {disposition} | {before} | {after} | {trigger_before} | {trigger_after} | {variables} | {parameters} | {consent} | {rationale} |".format(
                    order=_cell(item["source_order"]),
                    row=_cell(item["row_id"]),
                    source=_cell(item["source_locator"]),
                    disposition=_cell(item["disposition"]),
                    before=_cell(item["before_tag_name"]),
                    after=_cell(item["after_tag_name"]),
                    trigger_before=_cell(item["trigger_before"]),
                    trigger_after=_cell(item["trigger_after"]),
                    variables=_cell(item["variable_changes"]),
                    parameters=_cell(item["parameter_changes"]),
                    consent=_cell(item["consent_changes"]),
                    rationale=_cell(item["rationale"]),
                )
            )
    lines.extend(
        [
            "",
            "## Target results",
            "",
            "| Target | Container type | Status | Last verified operation | Recovery boundary |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for result in document["target_results"]:
        lines.append(
            f"| {_cell(result['target_id'])} | {_cell(types[result['target_id']])} | {_cell(result['status'])} | {_cell(result.get('last_verified_operation_id'))} | {_cell(result.get('recovery_boundary'))} |"
        )
    lines.extend(["", "## Analyst and developer object change log", ""])
    visible = [
        item
        for item in operations
        if item["action"] not in {"reuse", "untouched"}
        or item["state"] not in {"planned", "verified"}
    ]
    lines.append(
        f"Unchanged objects: {_cell(len(operations) - len(visible))}. Full evidence remains in the machine record."
    )
    lines.append("")
    if not visible:
        lines.append("No GTM object operation is recorded.")
    else:
        lines.extend(
            [
                "| Operation | Target | Resource | Action | State | Object | Requirements |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for operation in visible:
            lines.append(
                f"| {_cell(operation['operation_id'])} | {_cell(operation['target_id'])} | {_cell(operation['resource_family'])} | {_cell(operation['action'])} | {_cell(operation['state'])} | {_cell(operation['name'])} | {_cell(', '.join(operation['requirement_ids']))} |"
            )
        lines.append("")
    for operation in visible:
        lines.extend(
            [
                f"### [{_cell(operation['action'].upper())} / {_cell(operation['state'].upper())}] {_cell(operation['name'])}",
                "",
                f"- Rationale: {_cell(operation['justification'])}",
                "- Changed fields (before → intended): "
                + "; ".join(
                    (_cell(change) for change in semantic_field_changes(operation, document))
                ),
            ]
        )
        if "saved_readback" in operation:
            if operation["saved_readback"] is None:
                lines.append("- Saved object: absent")
            else:
                identifier = _saved_object_id(operation)
                lines.append(
                    f"- Saved object ID: {_cell(_cell(identifier) if identifier is not None else 'not recorded in readback')}"
                )
        if operation.get("comparison"):
            outcome = "passed" if operation["comparison"]["pass"] else "failed"
            lines.append(f"- Readback comparison: {_cell(outcome)}")
        if operation.get("replacement_reason"):
            lines.append(f"- Replacement reason: {_cell(operation['replacement_reason'])}")
        if operation.get("error"):
            lines.append(f"- Error: {_cell(operation['error'])}")
        lines.append("")
    lines.extend(["## Requirement, payload, and consent mapping", ""])
    for requirement in document["requirements"]:
        requirement_id = requirement["id"]
        mappings = [
            item
            for item in document["payload_mappings"]
            if item["requirement_id"] == requirement_id
        ]
        topologies = [
            item
            for item in document["consent_topologies"]
            if requirement_id in item.get("requirement_ids", [])
        ]
        lines.extend(
            [
                f"### {_cell(requirement_id)} — {_cell(requirement['status'])}",
                "",
                f"- Source event: {_cell(requirement.get('source_event') or 'not applicable')}",
                f"- Destination: {_cell(requirement.get('destination') or 'not supplied')}",
                "- Objects: " + _cell(", ".join(requirement.get("object_keys", [])) or "none"),
            ]
        )
        if topologies:
            for topology in topologies:
                if topology.get("consent_mode") == "client-policy-ungated":
                    policy = topology["web_enforcement"]["client_policy"]
                    lines.append(
                        f"- No consent gating (client policy): {_cell(policy['scope'])}; authorization {_cell(policy['locator'])}. This records the supplied implementation policy, not a legal determination."
                    )
                lines.append(
                    "- Consent {identifier}: authority {authority}; web {web}; server {server}; transport {transport}; unknown {unknown}".format(
                        identifier=_cell(topology["consent_topology_id"]),
                        authority=_cell(topology["signal_authority"]),
                        web=_cell(topology["web_enforcement"]["mechanism"]),
                        server=_cell(topology["server_enforcement"]["mechanism"]),
                        transport=_cell(topology["transport_behavior"]),
                        unknown=_cell(topology["unknown_state_behavior"]),
                    )
                )
        else:
            lines.append("- Consent: no topology applies to this requirement")
        for mapping in mappings:
            lines.append(
                "- Field {field}: {source} [{source_shape}] -> {method} -> {resolution} -> {template} [{destination_shape}] ({status})".format(
                    field=_cell(mapping["destination_field"]),
                    source=_cell(mapping.get("source") or "unresolved"),
                    source_shape=_cell(mapping.get("source_shape") or "shape unresolved"),
                    method=_cell(mapping.get("mapping_method") or "method unresolved"),
                    resolution=_cell(mapping.get("gtm_resolution") or "unresolved"),
                    template=_cell(mapping.get("template_field") or "unresolved"),
                    destination_shape=_cell(mapping.get("destination_shape") or "shape unresolved"),
                    status=_cell(mapping["status"]),
                )
            )
            if mapping["status"] == "mapped":
                binding = mapping.get("native_binding")
                owner = next(
                    (
                        item
                        for item in operations
                        if binding and item["object_key"] == binding["object_key"]
                    ),
                    {},
                )
                target = owner.get("intended") or owner.get("pre_change") or {}
                lines.append(
                    "  Mapping assurance: "
                    + (
                        f"exact native event-parameter intention checked at {_cell(binding['object_key'])} / {_cell(binding['field'])}; saved equality follows operation verification."
                        if binding and supports_native_mapping(mapping, target)
                        else "agent-reviewed mapping declaration; native field equality and source routing are not verified for this scope/structure or automatic/product behavior."
                    )
                )
        if not mappings:
            lines.append("- Payload fields: none recorded")
        lines.append("")
    lines.extend(["## Per-tag web execution topology", ""])
    if not document["execution_topologies"]:
        lines.append("No web tag topology is recorded.")
    for topology in document["execution_topologies"]:
        triggers = ", ".join(
            (
                f"{trigger['trigger_object_key']} [{trigger['role']}/{trigger['type']}]"
                for trigger in topology["normal_triggers"]
            )
        )
        lines.append(
            "- {tag}: {role}; triggers {triggers}; blocks {blocks}; consent {consent}; firing {firing}; pre-CMP {pre_cmp}; ecommerce {ecommerce}".format(
                tag=_cell(topology["tag_object_key"]),
                role=_cell(topology["lifecycle_role"]),
                triggers=_cell(triggers or "none"),
                blocks=_cell(", ".join(topology["blocking_trigger_keys"]) or "none"),
                consent=_cell(", ".join(topology.get("consent_topology_ids", [])) or "none"),
                firing=_cell(topology["firing_option"]),
                pre_cmp=_cell(topology["pre_cmp_policy"]),
                ecommerce=_cell(topology["ecommerce_route"]),
            )
        )
    lines.append("")
    lines.extend(["## Page-view and first-party-data decisions", ""])
    for decision in document["page_view_decisions"]:
        lines.append(
            f"- Page view {_cell(decision['destination'])} / {_cell(decision['occurrence'])}: {_cell(decision['owner'])}; send_page_view={_cell(str(decision['send_page_view']).lower() if decision['send_page_view'] is not None else 'not-applicable')}; Google tag={_cell(decision.get('google_tag_object_key') or 'none')}; {_cell(decision['reason'])}"
        )
    for route in document["first_party_data_routes"]:
        fields = ", ".join((item["name"] for item in route["fields"]))
        lines.append(
            f"- First-party data {_cell(route['requirement_id'])}: {_cell(route['feature'])}; destination={_cell(route['destination_field'])}; timing={_cell(route['timing'])}; hashing={_cell(route['hashing_owner'])}; keys={_cell(fields)}"
        )
    if not document["page_view_decisions"] and (not document["first_party_data_routes"]):
        lines.append("- No page-view-capable or first-party-data decision is in scope.")
    if document["pipelines"]:
        lines.extend(["", "## Client-to-server pipeline proof", ""])
        for pipeline in document["pipelines"]:
            lines.append(
                f"- {_cell(pipeline['pipeline_id'])}: {_cell(', '.join(pipeline['sending_target_ids']))} -> {_cell(pipeline['receiving_target_id'])} via {_cell(pipeline['request_class'])}; claiming Client operation {_cell(pipeline['claiming_client_operation_id'])}."
            )
            for flow in pipeline["event_flows"]:
                lines.append(
                    f"  - {_cell(flow['requirement_id'])}: {_cell(flow['source_event'])} -> {_cell(flow['transported_event'])} -> {_cell(', '.join(flow['server_consumer_operation_ids']))}"
                )
            for field in pipeline["field_flows"]:
                lines.append(
                    "  - Field [{status}] {source} -> {wire} -> {event_data} -> {destination}; requirements {requirements}; receiver {receiver}; transformation {transformation}".format(
                        status=_cell(field["status"]),
                        source=_cell(field["source"]["path"]),
                        wire=_cell(field["wire"]["path"]),
                        event_data=_cell(field["event_data"]["path"]),
                        destination=_cell(field["destination"]["path"]),
                        requirements=_cell(", ".join(field.get("requirement_ids", []))),
                        receiver=_cell(field.get("receiver_owner") or "none"),
                        transformation=_cell(field.get("transformation_owner") or "none"),
                    )
                )
    lines.extend(["", "## Browser/server deduplication", ""])
    if not document["dedup_contracts"]:
        lines.append("- No dual-delivery deduplication contract is in scope.")
    for contract in document["dedup_contracts"]:
        lines.append(
            f"- {_cell(contract['dedup_contract_id'])} / {_cell(contract['requirement_id'])}: {_cell(contract['strategy'])} from {_cell(contract['source_type'])}; event {_cell(contract['event_name'])}; source {_cell(contract.get('source_reference') or 'none')}; server path {_cell(contract.get('server_event_data_path') or 'none')}."
        )
    lines.extend(["", "## Official guidance applied", ""])
    for source in document["official_sources"]:
        lines.append(
            f"- {_source_link(source)} (accessed {_cell(source['access_date'])}; requirements {_cell(', '.join(source['supports']))}): {_cell(source['decision'])}"
        )
    lines.extend(["", "## External actions, publication, and recette", ""])
    if document["external_dependencies"]:
        for dependency in document["external_dependencies"]:
            lines.append(
                f"- External [{_cell(dependency['status'])}] {_cell(dependency['owner'])}: {_cell(dependency['action'])}"
            )
    else:
        lines.append("- No external dependency recorded.")
    if document["publication_dependencies"]:
        for item in document["publication_dependencies"]:
            lines.append(
                f"- Publication {_cell(item['kind'])}: {_cell(item['status'])}; depends on {_cell(item.get('depends_on_kind') or 'none')}; does not block saved configuration."
            )
    else:
        lines.append("- No server/pipeline publication sequence applies.")
    lines.extend(
        [
            "- Runtime GTM Preview/recette was not performed.",
            "- Publication and GTM version creation were not performed.",
            "",
            "## Machine-readable run record",
            "",
            "- Schema: configure-gtm/configuration-run@5.0",
            f"- Run ID: {_cell(run['id'])}",
            f"- Contract fingerprint: {_cell(run['contract']['fingerprint'])}",
        ]
    )
    if embed_machine:
        fence = "`" * max(
            3, 1 + max((len(match) for match in re.findall(r"`+", json.dumps(document))), default=0)
        )
        lines.extend(
            [
                "",
                fence + "json",
                json.dumps(
                    redact_for_persistence(
                        document, public_identifier_paths=public_identifier_paths(document)
                    ),
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=False,
                ),
                fence,
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
