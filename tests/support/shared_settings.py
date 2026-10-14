"""Synthetic approved repeated native GA4 settings graph for offline tests."""

from copy import deepcopy

from gtm_configure.domain.resources import semantic_object_key

from support.contracts import valid_web_contract


def parameter(name, value):
    return {"type": "template", "key": name, "value": value}


def event_row(name, value):
    return {
        "type": "map",
        "map": [parameter("parameter", name), parameter("parameterValue", value)],
    }


def repeated_request(count=3, fields=6):
    contract = valid_web_contract()
    objects = contract["implementation"]["objects"]
    block = next(item["object_key"] for item in objects if "denied" in item["name"])
    for field_index in range(fields):
        name = f"DLV - context_{field_index}"
        objects.append(
            {
                "target_id": "web-main",
                "resource_family": "variable",
                "name": name,
                "object_key": semantic_object_key("web-main", "variable", name),
                "action": "create",
                "requirement_ids": [f"REQ-EVENT-{index}" for index in range(count)],
                "depends_on": [],
                "justification": "Approved shared scalar source",
                "evidence": ["approved-input"],
                "risk": "routine",
                "intended": {
                    "type": "v",
                    "parameter": [
                        parameter("name", f"context.context_{field_index}"),
                        {"type": "integer", "key": "dataLayerVersion", "value": "2"},
                    ],
                },
            }
        )
    for index in range(count):
        requirement_id = f"REQ-EVENT-{index}"
        event = f"business_event_{index}"
        requirement = deepcopy(contract["requirements"][0])
        requirement.update(id=requirement_id, event_name=event, source_event=event, parameters={})
        for field_index in range(fields):
            requirement["parameters"][f"context_{field_index}"] = {
                "source": f"context.context_{field_index}",
                "source_shape": "scalar:string",
                "destination_shape": "scalar:string",
                "missing_behavior": "omit when absent",
                "provenance": {
                    "grade": "approved-input",
                    "locator": f"Approved business event {index}",
                },
            }
        contract["requirements"].append(requirement)
        trigger_name = f"CE - {event}"
        trigger_key = semantic_object_key("web-main", "trigger", trigger_name)
        tag_name = f"GA4 - {event}"
        tag_key = semantic_object_key("web-main", "tag", tag_name)
        for family, name, key, native, dependencies in [
            (
                "trigger",
                trigger_name,
                trigger_key,
                {
                    "type": "customEvent",
                    "customEventFilter": [
                        {
                            "type": "equals",
                            "parameter": [
                                parameter("arg0", "{{_event}}"),
                                parameter("arg1", event),
                            ],
                        },
                    ],
                },
                [],
            ),
            (
                "tag",
                tag_name,
                tag_key,
                {
                    "type": "gaawe",
                    "parameter": [
                        parameter("measurementIdOverride", "G-TEST123"),
                        parameter("eventName", event),
                        {
                            "type": "list",
                            "key": "eventSettingsTable",
                            "list": [
                                event_row(
                                    f"context_{field_index}", f"{{{{DLV - context_{field_index}}}}}"
                                )
                                for field_index in range(fields)
                            ],
                        },
                    ],
                    "firingTriggerId": [trigger_key],
                    "blockingTriggerId": [block],
                    "tagFiringOption": "oncePerEvent",
                },
                [trigger_key, block]
                + [item["object_key"] for item in objects if item["resource_family"] == "variable"],
            ),
        ]:
            objects.append(
                {
                    "target_id": "web-main",
                    "resource_family": family,
                    "name": name,
                    "object_key": key,
                    "action": "create",
                    "requirement_ids": [requirement_id],
                    "depends_on": dependencies,
                    "justification": "Approved business event",
                    "evidence": ["approved-input", "official-current"],
                    "risk": "routine",
                    "intended": native,
                }
            )
        contract["tag_policies"].append(
            {
                "tag_object_key": tag_key,
                "lifecycle_role": "event-driven",
                "trigger_roles": [{"trigger_object_key": trigger_key, "role": "source-event"}],
                "consent_policy_id": "CONSENT-GA4",
                "blocking_event_scope": ".*",
                "pre_cmp_policy": "not-applicable",
                "page_view_occurrences": [],
                "evidence": ["approved-input", "official-current"],
            }
        )
        contract["consent_policies"][0]["event_coverage"].append(event)
    for evidence in contract["evidence"]:
        if evidence["grade"] == "official-current":
            evidence["supports"] = [item["id"] for item in contract["requirements"]]
    implementation = contract.pop("implementation")
    contract.update(implementation)
    contract.pop("scope")
    for item in objects:
        item.pop("approval", None)
    return contract
