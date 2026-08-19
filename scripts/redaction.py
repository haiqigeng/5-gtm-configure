"""Redact credentials and user values before configure-gtm artifacts are persisted."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Protocol

REDACTED_STATE = "present-not-compared"
_SECRET_KEY = re.compile(
    r"(?:^|_)(?:access_?token|api_?key|authorization_?header|bearer_?token|client_?secret|credential|"
    r"password|private_?key|secret)(?:$|_)",
    re.IGNORECASE,
)
_PII_KEY = re.compile(
    r"^(?:email|email_address|emailaddress|em|phone|phone_number|phonenumber|ph|"
    r"street|street_address|first_name|firstname|fn|last_name|lastname|ln|user_city|ct|"
    r"user_region|st|postal_code|postalcode|zip|zp|external_id|user_id_value|"
    r"user_data_value|raw_user_data)$",
    re.IGNORECASE,
)
_EMAIL_VALUE = re.compile(r"(?<![\w.-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
_PHONE_VALUE = re.compile(r"(?<!\d)\+?\d(?:[\s().-]*\d){7,14}(?!\d)")
_AUTHORIZATION_VALUE = re.compile(
    r"^\s*(?:Bearer|Basic)\s+\S{8,}\s*$",
    re.IGNORECASE,
)
_GTM_REFERENCE = re.compile(r"^\{\{[^{}]+\}\}$")
_SAFE_METADATA_KEYS = {
    "destructive_authorization",
    "secret_comparison",
    "secret_fields",
}


def _is_protected_key(key: str) -> bool:
    """Distinguish actual sensitive fields from redaction audit metadata."""
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", key).replace("-", "_")
    normalized = normalized.casefold()
    if normalized in _SAFE_METADATA_KEYS:
        return False
    if normalized == "authorization":
        return True
    return key not in _SAFE_METADATA_KEYS and bool(
        _SECRET_KEY.search(normalized) or _PII_KEY.match(normalized)
    )


def _authorization_value_indexes(value: list[Any]) -> set[int]:
    """Locate GTM's flattened name/value row for an Authorization header."""
    has_authorization_name = any(
        isinstance(item, dict)
        and str(item.get("key", item.get("name", ""))).casefold() == "name"
        and str(item.get("value", item.get("defaultValue", ""))).strip().casefold()
        == "authorization"
        for item in value
    )
    if not has_authorization_name:
        return set()
    return {
        index
        for index, item in enumerate(value)
        if isinstance(item, dict)
        and str(item.get("key", item.get("name", ""))).strip().casefold() == "value"
        and ("value" in item or "defaultValue" in item)
    }


class SecretProvider(Protocol):
    """Ephemeral input interface; resolved values must never enter a run artifact."""

    def resolve(self, reference: str) -> str: ...


class SecretResolutionError(ValueError):
    """Raised when a redacted mutation field has no secure ephemeral value."""


def redacted_marker(*, reference: str | None = None) -> dict[str, str]:
    marker = {"secret_state": REDACTED_STATE}
    if reference:
        marker["reference"] = reference
    return marker


def is_redacted(value: Any) -> bool:
    return isinstance(value, dict) and value.get("secret_state") == REDACTED_STATE


def _literal_looks_sensitive(value: str) -> bool:
    stripped = value.strip()
    digit_count = sum(character.isdigit() for character in stripped)
    phone_like = (
        digit_count >= 9
        and (
            stripped.startswith("+")
            or any(ch in stripped for ch in " ().-")
            or bool(re.fullmatch(r"0\d{9}", stripped))
        )
        and bool(_PHONE_VALUE.fullmatch(stripped))
    )
    return bool(_EMAIL_VALUE.search(value) or phone_like or _AUTHORIZATION_VALUE.fullmatch(value))


def _is_safe_reference(value: Any) -> bool:
    if is_redacted(value):
        return True
    if isinstance(value, str):
        return bool(_GTM_REFERENCE.fullmatch(value.strip()))
    if isinstance(value, dict):
        reference = value.get("variable_reference") or value.get("secret_reference")
        return isinstance(reference, str) and bool(reference.strip())
    return False


def _is_configuration_descriptor(value: Any) -> bool:
    return isinstance(value, dict) and bool(
        set(value)
        & {
            "source",
            "source_path",
            "provenance",
            "source_shape",
            "destination_shape",
            "variable_reference",
            "key_path",
            "parameter",
            "field_name",
        }
    )


def redact_for_persistence(
    value: Any,
    *,
    exact_secret_paths: set[str] | None = None,
    path: str = "$",
) -> Any:
    """Return a deep redacted copy before write, diff, error, render, or handoff."""
    exact_secret_paths = set(exact_secret_paths or set())
    if is_redacted(value):
        return deepcopy(value)
    if path in exact_secret_paths:
        return redacted_marker()
    if isinstance(value, dict):
        declared = value.get("secret_fields")
        if isinstance(declared, list):
            exact_secret_paths.update(
                f"{path}.{item}" for item in declared if isinstance(item, str) and item.strip()
            )
        row_identifier = next(
            (
                value.get(field)
                for field in ("key", "name", "parameter", "field_name", "fieldName")
                if isinstance(value.get(field), str)
            ),
            None,
        )
        protected_row = isinstance(row_identifier, str) and _is_protected_key(row_identifier)
        output: dict[str, Any] = {}
        for key, child in value.items():
            child_path = f"{path}.{key}"
            protected_key = _is_protected_key(key)
            descriptor = bool(_PII_KEY.match(key)) and _is_configuration_descriptor(child)
            protected_row_value = protected_row and key in {"value", "defaultValue"}
            if (protected_key and not descriptor or protected_row_value) and not _is_safe_reference(
                child
            ):
                if child is None or child == "":
                    output[key] = child
                else:
                    output[key] = redacted_marker()
            else:
                output[key] = redact_for_persistence(
                    child,
                    exact_secret_paths=exact_secret_paths,
                    path=child_path,
                )
        return output
    if isinstance(value, list):
        authorization_indexes = _authorization_value_indexes(value)
        for index in authorization_indexes:
            item = value[index]
            if isinstance(item, dict):
                for field in ("value", "defaultValue"):
                    if field in item:
                        exact_secret_paths.add(f"{path}[{index}].{field}")
        return [
            redact_for_persistence(
                child,
                exact_secret_paths=exact_secret_paths,
                path=f"{path}[{index}]",
            )
            for index, child in enumerate(value)
        ]
    if isinstance(value, str) and _literal_looks_sensitive(value):
        return redacted_marker()
    return deepcopy(value)


def contains_redacted(value: Any) -> bool:
    if is_redacted(value):
        return True
    if isinstance(value, dict):
        return any(contains_redacted(child) for child in value.values())
    if isinstance(value, list):
        return any(contains_redacted(child) for child in value)
    return False


def safe_equal(left: Any, right: Any) -> bool:
    """Redacted values are deliberately incomparable, even to another marker."""
    if contains_redacted(left) or contains_redacted(right):
        return False
    return left == right


def resolve_for_mutation(value: Any, provider: SecretProvider | None) -> tuple[Any, set[str]]:
    """Resolve referenced markers in memory; callers must never persist the returned value."""
    resolved_values: set[str] = set()

    def visit(item: Any) -> Any:
        if is_redacted(item):
            reference = item.get("reference")
            if not isinstance(reference, str) or not reference.strip():
                raise SecretResolutionError("secret marker needs a secure reference")
            if provider is None:
                raise SecretResolutionError("no secret provider is bound to this target")
            resolved = provider.resolve(reference)
            if not isinstance(resolved, str) or not resolved:
                raise SecretResolutionError("secret provider returned an empty value")
            resolved_values.add(resolved)
            return resolved
        if isinstance(item, dict):
            return {key: visit(child) for key, child in item.items()}
        if isinstance(item, list):
            return [visit(child) for child in item]
        return deepcopy(item)

    return visit(value), resolved_values


def scrub_sensitive_text(value: str, sensitive_values: set[str]) -> str:
    """Remove ephemeral values from an exception before any persistence or display."""
    output = value
    for secret in sorted(sensitive_values, key=len, reverse=True):
        output = output.replace(secret, "[REDACTED]")
    return output


def sensitive_paths(
    value: Any,
    *,
    path: str = "$",
    exact_secret_paths: set[str] | None = None,
) -> list[str]:
    """Return paths that still contain a literal credential or user value."""
    exact_secret_paths = set(exact_secret_paths or set())
    findings: list[str] = []
    if is_redacted(value):
        return findings
    if path in exact_secret_paths and value not in (None, "") and not _is_safe_reference(value):
        return [path]
    if isinstance(value, dict):
        declared = value.get("secret_fields")
        if isinstance(declared, list):
            exact_secret_paths.update(
                f"{path}.{item}" for item in declared if isinstance(item, str) and item.strip()
            )
        row_identifier = next(
            (
                value.get(field)
                for field in ("key", "name", "parameter", "field_name", "fieldName")
                if isinstance(value.get(field), str)
            ),
            None,
        )
        protected_row = isinstance(row_identifier, str) and _is_protected_key(row_identifier)
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if (
                (_is_protected_key(key) or (protected_row and key in {"value", "defaultValue"}))
                and child not in (None, "")
                and not _is_safe_reference(child)
                and not (bool(_PII_KEY.match(key)) and _is_configuration_descriptor(child))
            ):
                if not is_redacted(child):
                    findings.append(child_path)
            findings.extend(
                sensitive_paths(
                    child,
                    path=child_path,
                    exact_secret_paths=exact_secret_paths,
                )
            )
    elif isinstance(value, list):
        authorization_indexes = _authorization_value_indexes(value)
        for index in authorization_indexes:
            item = value[index]
            if isinstance(item, dict):
                for field in ("value", "defaultValue"):
                    if field in item:
                        exact_secret_paths.add(f"{path}[{index}].{field}")
        for index, child in enumerate(value):
            findings.extend(
                sensitive_paths(
                    child,
                    path=f"{path}[{index}]",
                    exact_secret_paths=exact_secret_paths,
                )
            )
    elif isinstance(value, str) and _literal_looks_sensitive(value):
        findings.append(path)
    return sorted(set(findings))
