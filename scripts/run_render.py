"""Human configuration-result rendering for configuration-run@4.0."""

from __future__ import annotations

import json
from typing import Any

from redaction import redact_for_persistence


def _cell(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def render_markdown(document: dict[str, Any], *, embed_machine: bool = False) -> str:
    run = document["run"]
    operations = document["object_changes"]
    counts: dict[str, int] = {}
    for operation in operations:
        counts[operation["action"]] = counts.get(operation["action"], 0) + 1
    preview = run["phase"] == "preflight" and all(
        operation["state"] == "planned" for operation in operations
    )
    heading = "Pre-mutation impact preview" if preview else "GTM configuration result"
    lines = [
        f"# {heading}",
        "",
        "## Executive summary",
        "",
        f"- Verdict: **{run['status']}**",
        f"- Run: `{run['id']}`; mode: `{run['mode']}`; phase: `{run['phase']}`",
        f"- Requirements: {len(document['requirements'])}",
        f"- Execution mode: `{run['execution_mode']}`",
        "- Intended object actions: "
        + (", ".join(f"{key} {value}" for key, value in sorted(counts.items())) or "none"),
        f"- Consent topologies: {len(document['consent_topologies'])}",
        f"- Pipelines: {len(document['pipelines'])}",
        "- Publication: not performed; no GTM version created",
        "- Runtime recette: not performed",
        "",
        "## Targets and baseline",
        "",
        "| Target | Type | Account | Container | Workspace | Baseline complete | Existing changes |",
        "| --- | --- | --- | --- | --- | --- | ---: |",
    ]
    types = {target["target_id"]: target["container_type"] for target in document["run"]["targets"]}
    baselines = {item["target_id"]: item for item in document["container_baselines"]}
    for target in run["targets"]:
        baseline = baselines[target["target_id"]]
        lines.append(
            f"| {_cell(target['target_id'])} | {_cell(target['container_type'])} | "
            f"{_cell(target['account_id'])} | {_cell(target['container_id'])} | "
            f"{_cell(target['workspace_id'])} | {_cell(baseline['complete'])} | "
            f"{_cell(baseline.get('preexisting_workspace_changes'))} |"
        )

    if document["inventory_dispositions"]:
        lines.extend(
            [
                "",
                "## Inventory-aligned tag change log",
                "",
                "| Order | Source row | Vendor/source | Disposition | Tag before | Tag after | "
                "Trigger before | Trigger after | Variable changes | Parameter changes | Consent "
                "changes | Rationale |",
                "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in sorted(
            document["inventory_dispositions"], key=lambda value: value["source_order"]
        ):
            lines.append(
                "| {order} | {row} | {source} | {disposition} | {before} | {after} | "
                "{trigger_before} | {trigger_after} | {variables} | {parameters} | {consent} | "
                "{rationale} |".format(
                    order=item["source_order"],
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
            f"| {_cell(result['target_id'])} | {_cell(types[result['target_id']])} | "
            f"{_cell(result['status'])} | {_cell(result.get('last_verified_operation_id'))} | "
            f"{_cell(result.get('recovery_boundary'))} |"
        )

    lines.extend(
        [
            "",
            "## Analyst and developer object change log",
            "",
        ]
    )
    if not operations:
        lines.append("No GTM object operation is recorded.")
    else:
        lines.extend(
            [
                "| Operation | Target | Resource | Action | State | Object | Requirements |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for operation in operations:
            lines.append(
                f"| {_cell(operation['operation_id'])} | {_cell(operation['target_id'])} | "
                f"{_cell(operation['resource_family'])} | {_cell(operation['action'])} | "
                f"{_cell(operation['state'])} | {_cell(operation['name'])} | "
                f"{_cell(', '.join(operation['requirement_ids']))} |"
            )
        lines.append("")
    for operation in operations:
        intended = operation.get("intended", {})
        lines.extend(
            [
                f"### [{operation['action'].upper()} / {operation['state'].upper()}] "
                f"{operation['name']}",
                "",
                f"- Target/resource: `{operation['target_id']}` / `{operation['resource_family']}`",
                f"- Object key: `{operation['object_key']}`",
                "- Requirements: " + (", ".join(operation["requirement_ids"]) or "none"),
                "- Dependencies: " + (", ".join(operation["dependencies"]) or "none"),
                f"- Rationale: {operation['justification']}",
                "- Evidence: " + (", ".join(operation["evidence"]) or "none"),
                f"- Type: `{intended.get('type', 'not applicable')}`",
                "- Firing triggers: " + (", ".join(intended.get("firingTriggerId", [])) or "none"),
                "- Blocking triggers: "
                + (", ".join(intended.get("blockingTriggerId", [])) or "none"),
            ]
        )
        if operation.get("replacement_reason"):
            lines.append(f"- Replacement reason: {operation['replacement_reason']}")
        if operation.get("error"):
            lines.append(f"- Error: {operation['error']}")
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
                f"### {requirement_id} — {requirement['status']}",
                "",
                f"- Source event: `{requirement.get('source_event') or 'not applicable'}`",
                f"- Destination: `{requirement.get('destination') or 'not supplied'}`",
                "- Objects: " + (", ".join(requirement.get("object_keys", [])) or "none"),
            ]
        )
        if topologies:
            for topology in topologies:
                lines.append(
                    "- Consent `{identifier}`: authority `{authority}`; web `{web}`; server "
                    "`{server}`; transport `{transport}`; unknown `{unknown}`".format(
                        identifier=topology["consent_topology_id"],
                        authority=topology["signal_authority"],
                        web=topology["web_enforcement"]["mechanism"],
                        server=topology["server_enforcement"]["mechanism"],
                        transport=topology["transport_behavior"],
                        unknown=topology["unknown_state_behavior"],
                    )
                )
        else:
            lines.append("- Consent: no topology applies to this requirement")
        for mapping in mappings:
            lines.append(
                "- Field `{field}`: `{source}` [{source_shape}] -> {method} -> `{resolution}` "
                "-> `{template}` [{destination_shape}] ({status})".format(
                    field=mapping["destination_field"],
                    source=mapping.get("source") or "unresolved",
                    source_shape=mapping.get("source_shape") or "shape unresolved",
                    method=mapping.get("mapping_method") or "method unresolved",
                    resolution=mapping.get("gtm_resolution") or "unresolved",
                    template=mapping.get("template_field") or "unresolved",
                    destination_shape=mapping.get("destination_shape") or "shape unresolved",
                    status=mapping["status"],
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
            f"{trigger['trigger_object_key']} [{trigger['role']}/{trigger['type']}]"
            for trigger in topology["normal_triggers"]
        )
        lines.append(
            "- `{tag}`: {role}; triggers {triggers}; blocks {blocks}; consent {consent}; "
            "firing {firing}; pre-CMP {pre_cmp}; ecommerce {ecommerce}".format(
                tag=topology["tag_object_key"],
                role=topology["lifecycle_role"],
                triggers=triggers or "none",
                blocks=", ".join(topology["blocking_trigger_keys"]) or "none",
                consent=", ".join(topology.get("consent_topology_ids", [])) or "none",
                firing=topology["firing_option"],
                pre_cmp=topology["pre_cmp_policy"],
                ecommerce=topology["ecommerce_route"],
            )
        )
    lines.append("")

    lines.extend(["## Page-view and first-party-data decisions", ""])
    for decision in document["page_view_decisions"]:
        lines.append(
            f"- Page view `{decision['destination']}` / `{decision['occurrence']}`: "
            f"{decision['owner']}; send_page_view="
            f"{str(decision['send_page_view']).lower() if decision['send_page_view'] is not None else 'not-applicable'}; "
            f"Google tag={decision.get('google_tag_object_key') or 'none'}; "
            f"{decision['reason']}"
        )
    for route in document["first_party_data_routes"]:
        fields = ", ".join(item["name"] for item in route["fields"])
        lines.append(
            f"- First-party data `{route['requirement_id']}`: {route['feature']}; "
            f"destination={route['destination_field']}; timing={route['timing']}; "
            f"hashing={route['hashing_owner']}; keys={fields}"
        )
    if not document["page_view_decisions"] and not document["first_party_data_routes"]:
        lines.append("- No page-view-capable or first-party-data decision is in scope.")

    if document["pipelines"]:
        lines.extend(["", "## Client-to-server pipeline proof", ""])
        for pipeline in document["pipelines"]:
            lines.append(
                f"- `{pipeline['pipeline_id']}`: "
                f"{', '.join(pipeline['sending_target_ids'])} -> "
                f"{pipeline['receiving_target_id']} via `{pipeline['request_class']}`; "
                f"claiming Client operation `{pipeline['claiming_client_operation_id']}`."
            )
            for flow in pipeline["event_flows"]:
                lines.append(
                    f"  - `{flow['requirement_id']}`: `{flow['source_event']}` -> "
                    f"`{flow['transported_event']}` -> "
                    f"{', '.join(flow['server_consumer_operation_ids'])}"
                )
            for field in pipeline["field_flows"]:
                lines.append(
                    "  - Field [{status}] `{source}` -> `{wire}` -> `{event_data}` -> "
                    "`{destination}`; requirements {requirements}; receiver `{receiver}`; "
                    "transformation `{transformation}`".format(
                        status=field["status"],
                        source=field["source"]["path"],
                        wire=field["wire"]["path"],
                        event_data=field["event_data"]["path"],
                        destination=field["destination"]["path"],
                        requirements=", ".join(field.get("requirement_ids", [])),
                        receiver=field.get("receiver_owner") or "none",
                        transformation=field.get("transformation_owner") or "none",
                    )
                )

    lines.extend(["", "## Browser/server deduplication", ""])
    if not document["dedup_contracts"]:
        lines.append("- No dual-delivery deduplication contract is in scope.")
    for contract in document["dedup_contracts"]:
        lines.append(
            f"- `{contract['dedup_contract_id']}` / `{contract['requirement_id']}`: "
            f"{contract['strategy']} from `{contract['source_type']}`; event "
            f"`{contract['event_name']}`; source `{contract.get('source_reference') or 'none'}`; "
            f"server path `{contract.get('server_event_data_path') or 'none'}`."
        )

    lines.extend(["", "## Official guidance applied", ""])
    for source in document["official_sources"]:
        lines.append(
            f"- [{source['title']}]({source['url']}) (accessed {source['access_date']}; "
            f"requirements {', '.join(source['supports'])}): {source['decision']}"
        )

    lines.extend(
        [
            "",
            "## External actions, publication, and recette",
            "",
        ]
    )
    if document["external_dependencies"]:
        for dependency in document["external_dependencies"]:
            lines.append(
                f"- External [{dependency['status']}] {dependency['owner']}: {dependency['action']}"
            )
    else:
        lines.append("- No external dependency recorded.")
    if document["publication_dependencies"]:
        for item in document["publication_dependencies"]:
            lines.append(
                f"- Publication `{item['kind']}`: `{item['status']}`; depends on "
                f"`{item.get('depends_on_kind') or 'none'}`; does not block saved configuration."
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
            "- Schema: `configure-gtm/configuration-run@4.0`",
            f"- Run ID: `{run['id']}`",
            f"- Contract fingerprint: `{run['contract']['fingerprint']}`",
        ]
    )
    if embed_machine:
        lines.extend(
            [
                "",
                "```json",
                json.dumps(
                    redact_for_persistence(document),
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=False,
                ),
                "```",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
