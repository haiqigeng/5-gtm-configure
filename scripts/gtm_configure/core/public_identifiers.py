"""Evidence-bound exemptions for public collection identifiers, never credentials.

The agent must inspect the cited official/template evidence. These records bind that
decision to an exact native field and literal; they do not authenticate its author.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urlsplit

from gtm_configure.core.schemas import definition_validator
from gtm_configure.core.template_source import canonical_template_source, valid_source_integrity


def _matches_reviewed_template(literal: Any, record: dict, declaration: dict) -> bool:
    if (
        declaration.get("classification") != "inspected-template-source"
        or declaration["path"] != ["templateData"]
        or not isinstance(literal, str)
    ):
        return False
    # Re-establish exact digest provenance before allowing representation changes.
    for field, digest_key in (
        ("intended", "value_sha256"),
        ("pre_change", "previous_value_sha256"),
    ):
        source = (record.get(field) or {}).get("templateData")
        if _matches(source, declaration.get(digest_key)) and canonical_template_source(
            literal
        ) == canonical_template_source(source):
            return True
    return False


def _records(value: Any) -> list[dict]:
    if not isinstance(value, dict):
        return []
    if "object_changes" in value:
        return value["object_changes"]
    if "implementation" in value:
        return value["implementation"].get("objects", [])
    return value.get("objects", []) + value.get("reuse_candidates", [])


def locate(value: Any, path: list) -> tuple[Any, str]:
    actual = []
    for part in path:
        if isinstance(value, list) and isinstance(part, str):
            matches = [
                index
                for index, item in enumerate(value)
                if isinstance(item, dict) and item.get("key") == part
            ]
            if len(matches) != 1:
                raise KeyError("Native keyed field must resolve uniquely")
            part = matches[0]
        actual.append(part)
        value = value[part]
    return value, _suffix(actual)


def _suffix(path: list) -> str:
    return "".join(f"[{part}]" if type(part) is int else "." + part for part in path)


def _matches(value: Any, digest: str) -> bool:
    return isinstance(value, str) and hashlib.sha256(value.encode("utf-8")).hexdigest() == digest


def validate_public_identifiers(document: dict) -> None:
    sources = {
        item.get("url", item.get("locator"))
        for item in document.get("official_sources", document.get("evidence", []))
        if "url" in item or item.get("grade") == "official-current"
    }
    for record in _records(document):
        declarations = record.get("public_identifiers", [])
        if not isinstance(declarations, list):
            raise ValueError("public_identifiers must be an array")
        seen = set()
        for declaration in declarations:
            if not definition_validator("publicIdentifier").is_valid(declaration):
                raise ValueError(
                    "public identifier needs exact path, value_sha256, source_url and reason"
                )
            path = declaration["path"]
            template_fixture = declaration.get("classification") == "inspected-template-source"
            if "classification" in declaration and not template_fixture:
                raise ValueError("Unsupported public source classification")
            if template_fixture and (
                path != ["templateData"]
                or (record.get("resource_family") or record.get("object_type")) != "template"
            ):
                raise ValueError("Template fixtures must bind the exact templateData source")
            if path == ["templateData"] and not template_fixture:
                raise ValueError(
                    "Template source requires inspected-template-source classification"
                )
            if (
                not isinstance(path, list)
                or not path
                or any(
                    not (
                        type(part) is int
                        and part >= 0
                        or isinstance(part, str)
                        and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part)
                    )
                    for part in path
                )
                or path[0]
                in {
                    "name",
                    "type",
                    "notes",
                    "fingerprint",
                    "accountId",
                    "containerId",
                    "workspaceId",
                }
            ):
                raise ValueError("public identifier path must name one native value field")
            if tuple(path) in seen:
                raise ValueError("duplicate public identifier path")
            seen.add(tuple(path))
            digest = declaration["value_sha256"]
            if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise ValueError(
                    "public identifier value_sha256 must be a lowercase SHA-256 digest"
                )
            try:
                native = (
                    record["pre_change"] if record.get("action") == "remove" else record["intended"]
                )
                literal, _ = locate(native, path)
            except (KeyError, TypeError, IndexError) as exc:
                raise ValueError(
                    "public identifier path does not resolve in intended native fields"
                ) from exc
            source_proved = (
                template_fixture
                and isinstance(literal, dict)
                and valid_source_integrity(literal.get("source_integrity"))
                and literal["source_integrity"]["source_sha256"] == digest
            )
            if (
                not (_matches(literal, digest) or source_proved)
                or not literal
                or isinstance(literal, str)
                and literal.strip().startswith("{{")
            ):
                raise ValueError(
                    "public identifier declaration must bind the exact intended literal"
                )
            if not template_fixture and not isinstance(native.get("type"), str):
                raise ValueError("public identifier classification needs the inspected native type")
            if "previous_value_sha256" in declaration:
                previous = declaration["previous_value_sha256"]
                try:
                    previous_value, _ = locate(record["pre_change"], path)
                except (KeyError, TypeError, IndexError) as exc:
                    raise ValueError(
                        "previous public identifier needs the matching pre_change field"
                    ) from exc
                if (
                    not isinstance(previous, str)
                    or not re.fullmatch(r"[a-f0-9]{64}", previous)
                    or not (
                        _matches(previous_value, previous)
                        or template_fixture
                        and isinstance(previous_value, dict)
                        and valid_source_integrity(previous_value.get("source_integrity"))
                        and previous_value["source_integrity"]["source_sha256"] == previous
                    )
                ):
                    raise ValueError("previous public identifier digest must bind pre_change")
            url = declaration["source_url"]
            if not isinstance(url, str) or url not in sources or urlsplit(url).scheme != "https":
                raise ValueError(
                    "public identifier source_url must reference recorded official-current evidence"
                )
            if not isinstance(declaration["reason"], str) or not declaration["reason"].strip():
                raise ValueError(
                    "public identifier classification needs its inspected field purpose"
                )


def public_identifier_paths(value: Any, *, records: list[dict] | None = None) -> set[str]:
    """Resolve caller-validated declarations across native bodies and saved graphs.

    Only exact same-name/type/target and same-value fields are exempted. A changed
    value or an unrelated object receives no exemption. Strong literal detectors
    in redaction.py still run even on these paths.
    """
    candidates = [
        item
        for item in (records if records is not None else _records(value))
        if item.get("public_identifiers")
    ]
    paths: set[str] = set()
    if not candidates:
        return paths

    def walk(item: Any, here: str, target: str | None, name: str | None) -> None:
        if isinstance(item, dict):
            target = item.get("target_id", target)
            name = item.get("name", name)
            matches = [
                record
                for record in candidates
                if (target is None or record.get("target_id") == target)
                and (
                    name in {record.get("name"), record.get("new_name", record.get("name"))}
                    or here == "$"
                    and records is not None
                    and len(candidates) == 1
                )
                and item.get("type")
                == (
                    record.get("pre_change", {})
                    if record.get("action") == "remove"
                    else record.get("intended", {})
                ).get("type")
            ]
            if len(matches) == 1:
                for declaration in matches[0]["public_identifiers"]:
                    try:
                        literal, suffix = locate(item, declaration["path"])
                    except (KeyError, IndexError, TypeError):
                        continue
                    if any(
                        _matches(literal, digest)
                        for digest in (
                            declaration["value_sha256"],
                            declaration.get("previous_value_sha256"),
                        )
                    ) or _matches_reviewed_template(literal, matches[0], declaration):
                        paths.add(here + suffix)
            for key, child in item.items():
                walk(child, f"{here}.{key}", target, name)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{here}[{index}]", target, name)

    walk(value, "$", None, None)
    return paths
