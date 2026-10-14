"""Custom-template source identity and content integrity, independent of resource IDs."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from gtm_configure.core.json_io import loads_strict


def template_sections(value: str) -> dict[str, str]:
    """Read unique native sections; ambiguous source has no inspectable identity."""
    sections = re.split(
        r"(?m)^(___[A-Z_]+___)[ \t]*$", value.lstrip("\ufeff").replace("\r\n", "\n")
    )
    headers = sections[1::2]
    if not headers or len(headers) != len(set(headers)):
        raise ValueError("Template source requires unique native sections")
    return dict(zip(headers, sections[2::2]))


def canonical_template_source(value: str) -> str:
    """Normalize native serialization while preserving code, permissions and INFO."""
    try:
        sections = template_sections(value)
        normalized = value.lstrip("\ufeff").replace("\r\n", "\n")
        output = [normalized.split(next(iter(sections)), 1)[0].strip()]
        for header, body in sections.items():
            body = body.strip()
            if header in {
                "___INFO___",
                "___TEMPLATE_PARAMETERS___",
                "___WEB_PERMISSIONS___",
                "___SERVER_PERMISSIONS___",
            }:
                body = json.dumps(
                    loads_strict(body),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                )
            output.extend((header, body))
        return "\n".join(output)
    except (ValueError, TypeError):
        return value


def template_source_integrity(value: str) -> dict[str, str]:
    """Retain full-content proof even when privacy classification redacts the body."""
    return {
        "source_sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
        "canonical_sha256": hashlib.sha256(
            canonical_template_source(value).encode("utf-8")
        ).hexdigest(),
    }


def valid_source_integrity(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"source_sha256", "canonical_sha256"}
        and all(
            isinstance(digest, str) and re.fullmatch(r"[a-f0-9]{64}", digest)
            for digest in value.values()
        )
    )


def valid_source_inspection(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"native_type", "parameter_types"}
        and isinstance(value["native_type"], str)
        and re.fullmatch(r"cvt_[A-Za-z0-9_]+", value["native_type"]) is not None
        and isinstance(value["parameter_types"], dict)
        and all(
            isinstance(name, str)
            and bool(name)
            and (kind is None or isinstance(kind, str) and kind in {"template", "boolean", "list"})
            for name, kind in value["parameter_types"].items()
        )
    )


def inspect_template_identity(source: str) -> str:
    """Bind a consumer type to installed INFO.id, never to templateId or gallery ID."""
    info = loads_strict(template_sections(source).get("___INFO___", "null"))
    native_type = info.get("id") if isinstance(info, dict) else None
    if not isinstance(native_type, str) or not re.fullmatch(r"cvt_[A-Za-z0-9_]+", native_type):
        raise ValueError("Installed template INFO.id must establish its native cvt consumer type")
    return native_type


def inspect_template_source(source: str) -> dict[str, Any]:
    """Inspect identity and field capability independently; unknown widgets stay unresolved.

    Native controls follow Google's template style guide. Multiline text remains
    TEXT; RADIO is a scalar choice. A None shape keeps an identity inspectable while
    preventing the compiler from claiming support for that field.
    https://developers.google.com/tag-platform/tag-manager/templates/style
    """
    native_type = inspect_template_identity(source)
    sections = template_sections(source)
    parameter_types = {}

    def inspect_fields(fields: Any) -> None:
        if not isinstance(fields, list):
            raise ValueError("Template parameters must be native field definitions")
        for field in fields:
            if not isinstance(field, dict):
                raise ValueError("Template field definition must be an object")
            field_type = field.get("type")
            if field_type == "GROUP":
                inspect_fields(field.get("subParams", []))
            elif field_type == "LABEL":
                continue
            else:
                kind = {
                    "TEXT": "template",
                    "SELECT": "template",
                    "RADIO": "template",
                    "CHECKBOX": "boolean",
                    "SIMPLE_TABLE": "list",
                    # Installed native PARAM_TABLE definitions and their runCode
                    # fixtures establish the same array-of-objects container.
                    "PARAM_TABLE": "list",
                }.get(field_type)
                name = field.get("name")
                if not isinstance(name, str) or not name or name in parameter_types:
                    raise ValueError("Template input requires a unique native field name")
                parameter_types[name] = kind

    inspect_fields(loads_strict(sections.get("___TEMPLATE_PARAMETERS___", "[]")))
    return {
        "native_type": native_type,
        "parameter_types": parameter_types,
        **template_source_integrity(source),
    }
