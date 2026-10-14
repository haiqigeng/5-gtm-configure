"""Resolve field ownership and dependency readiness for one validated operation graph."""

from graphlib import TopologicalSorter

from gtm_configure.domain.graph import served_requirements
from gtm_configure.domain.resources import required_baseline_families


def _field_blockers(document, operations):
    by_key = {op["object_key"]: key for key, op in operations.items()}
    direct = {key: set() for key in operations}
    requirements = {}

    def bind(requirement, owner_key, reason):
        requirements.setdefault(requirement, set()).add(reason)
        direct[by_key[owner_key]].add(reason)

    for row in document["payload_mappings"]:
        if row["status"] in {"pending", "blocked"}:
            bind(
                row["requirement_id"],
                row["owner_object_key"],
                f"{row['requirement_id']}: field {row['field_scope']}::{row['destination_field']} is {row['status']}",
            )
    for pipeline in document["pipelines"]:
        for row in pipeline["field_flows"]:
            if row["status"] != "proved":
                for req in row["requirement_ids"]:
                    bind(
                        req,
                        row["receiver_owner"],
                        f"{req}: pipeline field {row['destination_field']} is {row['status']}",
                    )
    for key, served in served_requirements(operations).items():
        if served and served <= requirements.keys():
            direct[key].update(reason for req in served for reason in requirements[req])
    return direct


def operation_readiness(document):
    """Shared dependencies serve any ready requirement; blocked owners remain indivisible.

    Field owners are explicit; dependency demand is derived independently of authorization.
    Blocker origins propagate forward through the graph; ordinary dependencies whose
    operations can still complete remain waiting until verified.
    """
    operations = {op["operation_id"]: op for op in document["object_changes"]}
    order = tuple(
        TopologicalSorter(
            {key: op["dependencies"] for key, op in operations.items()}
        ).static_order()
    )
    fields = _field_blockers(document, operations)
    missing_baselines = {
        row["target_id"]
        for row in document["container_baselines"]
        if row.get("complete") is not True
        or not required_baseline_families(
            [item for item in operations.values() if item["target_id"] == row["target_id"]],
            next(
                target["container_type"]
                for target in document["run"]["targets"]
                if target["target_id"] == row["target_id"]
            ),
        )
        <= set(row["resource_families"])
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
