"""Bind configured custom consumers to their inspected installed native template."""

from gtm_configure.core.template_source import inspect_template_source


def validate_template_bindings(operations, fail, *, persisted=False):
    by_id = {item["operation_id"]: item for item in operations}
    for consumer in operations:
        if consumer["resource_family"] not in {"tag", "variable", "client"} or consumer[
            "action"
        ] in {"remove", "pause"}:
            continue
        native = consumer.get("intended") or consumer.get("pre_change") or {}
        native_type = native.get("type", "")
        if not isinstance(native_type, str) or not native_type.startswith("cvt_"):
            continue
        templates = [
            by_id[key]
            for key in consumer["dependencies"]
            if by_id[key]["resource_family"] == "template"
        ]
        if not templates and consumer["action"] in {"reuse", "untouched"}:
            continue
        inspected = []
        for template in templates:
            source = (template.get("intended") or template.get("pre_change") or {}).get(
                "templateData"
            )
            try:
                if isinstance(source, str):
                    proof = inspect_template_source(source)
                elif (
                    persisted
                    and isinstance(source, dict)
                    and source.get("source_integrity")
                    and source.get("source_inspection")
                ):
                    proof = source["source_inspection"]
                else:
                    raise ValueError(
                        "installed source must establish native template identity and parameters"
                    )
                if proof["native_type"] == native_type:
                    inspected.append(proof)
            except (ValueError, KeyError, TypeError) as exc:
                fail(f"custom template {template['object_key']!r}: {exc}")
        if len(inspected) != 1:
            fail(
                f"custom consumer {consumer['object_key']!r} needs exactly one matching installed source dependency; INFO.id owns native type"
            )
            continue
        declared = inspected[0]["parameter_types"]
        for parameter in native.get("parameter", []):
            key = parameter.get("key")
            if (
                key not in declared
                or declared[key] is None
                or str(parameter.get("type", "")).casefold() != str(declared[key]).casefold()
            ):
                fail(
                    f"custom consumer {consumer['object_key']!r} parameter {key!r} requires its inspected template definition and native shape"
                )
