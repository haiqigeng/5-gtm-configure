"""Resolve field ownership and dependency readiness for one validated operation graph."""

from graphlib import TopologicalSorter

from gtm_configure.domain.graph import active_tag
from gtm_configure.domain.native import native_mapping_scope


def _field_owners(operations, order):
    """Native namespaces select owners; terminal tags consume unclassified fields."""
    downstream_tags = {key: set() for key in operations}
    downstream_requirements = {key: set() for key in operations}
    owners, terminals, scoped = {}, {}, {}
    for key in reversed(order):
        operation = operations[key]
        labels = {(operation["target_id"], req) for req in operation["requirement_ids"]}
        scope = native_mapping_scope(operation.get("intended") or operation.get("pre_change") or {})
        for req in operation["requirement_ids"]:
            if active_tag(operation) and scope is not None:
                scoped.setdefault((req, scope), set()).add(key)
            if req not in downstream_requirements[key]:
                terminals.setdefault(req, set()).add(key)
            if active_tag(operation) and (operation["target_id"], req) not in downstream_tags[key]:
                owners.setdefault(req, set()).add(key)
        for dependency in operation["dependencies"]:
            downstream_requirements[dependency].update(downstream_requirements[key])
            downstream_requirements[dependency].update(operation["requirement_ids"])
            downstream_tags[dependency].update(downstream_tags[key])
            if active_tag(operation):
                downstream_tags[dependency].update(labels)
    return {req: owners.get(req, keys) for req, keys in terminals.items()}, scoped


def _field_blockers(document, operations, order):
    owners, scoped = _field_owners(operations, order)
    by_key = {op["object_key"]: key for key, op in operations.items()}
    direct = {key: set() for key in operations}
    requirements = {}

    def bind(requirement, reason, binding=None, scope=None):
        requirements.setdefault(requirement, set()).add(reason)
        owner = by_key.get((binding or {}).get("object_key"))
        consumers = (
            {owner}
            if owner is not None and requirement in operations[owner]["requirement_ids"]
            else scoped.get((requirement, scope), owners.get(requirement, set()))
        )
        for key in consumers:
            direct[key].add(reason)

    for row in document["payload_mappings"]:
        if row["status"] in {"pending", "blocked"}:
            bind(
                row["requirement_id"],
                f"{row['requirement_id']}: field {row['field_scope']}::{row['destination_field']} is {row['status']}",
                row.get("native_binding"),
                row["field_scope"],
            )
    for pipeline in document["pipelines"]:
        for row in pipeline["field_flows"]:
            if row["status"] != "proved":
                for req in row["requirement_ids"]:
                    bind(
                        req, f"{req}: pipeline field {row['destination_field']} is {row['status']}"
                    )
    for key, operation in operations.items():
        served = set(operation["requirement_ids"])
        if served and served <= requirements.keys():
            direct[key].update(reason for req in served for reason in requirements[req])
    return direct


def operation_readiness(document):
    """Shared dependencies serve any ready requirement; blocked owners remain indivisible.

    Requirement attribution includes dependency consumers and is not field ownership.
    Blocker origins propagate forward through the graph; ordinary dependencies whose
    operations can still complete remain waiting until verified.
    """
    operations = {op["operation_id"]: op for op in document["object_changes"]}
    order = tuple(
        TopologicalSorter(
            {key: op["dependencies"] for key, op in operations.items()}
        ).static_order()
    )
    fields = _field_blockers(document, operations, order)
    missing_baselines = {
        row["target_id"]
        for row in document["container_baselines"]
        if row.get("complete") is not True
    }
    authentication_blocked = {
        op["target_id"]
        for op in operations.values()
        if op["state"] in {"failed", "uncertain"}
        and op.get("journal")
        and str(op["journal"][-1].get("error", "")).startswith("authentication_required:")
    }
    origins, result = {}, {}
    for key in order:
        op = operations[key]
        reasons = {(key, reason) for reason in fields[key]}
        if op["target_id"] in missing_baselines:
            reasons.add((key, "complete target baseline required"))
        if op["target_id"] in authentication_blocked:
            reasons.add((key, "target authentication requires revalidation"))
        for dependency in op["dependencies"]:
            if operations[dependency]["state"] != "verified":
                reasons.update(origins[dependency])
                if operations[dependency]["state"] in {"failed", "uncertain", "skipped"}:
                    reasons.add((dependency, f"operation is {operations[dependency]['state']}"))
        origins[key] = reasons
        result[key] = {
            "blocked": sorted(f"{origin}: {reason}" for origin, reason in reasons),
            "waiting": sorted(
                dep for dep in op["dependencies"] if operations[dep]["state"] != "verified"
            )
            if not reasons
            else [],
        }
    return result
