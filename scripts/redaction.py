"""Shared structural detection for persistence, write gating and exposure reports.

The scanner does not execute JavaScript or recognize arbitrary encoded secrets.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlsplit

REDACTED_STATE = "present-not-compared"
_SECRET_KEY = re.compile(
    r"(?:^|_)(?:token|tokens|api_?key|api_?secret|authorization|auth_?header|"
    r"client_?secret|credentials?|password|passwd|passphrase|private_?key|"
    r"consumer_?key|consumer_?secret|subscription_?key|access_?key|hapikey|"
    r"oauth|ck|cs|secret)(?:$|_)",
    re.IGNORECASE,
)
_PRIVATE_FIELD = re.compile(
    r"(?:^|_)(?:authorization|auth_?header|credentials?|password|passwd|passphrase|"
    r"private_?key|secret|oauth|hapikey|consumer_?key|subscription_?key|access_?key|"
    r"(?:access|refresh|capi)_?token)(?:$|_)",
    re.IGNORECASE,
)
_PII_KEY = re.compile(
    r"^(?:email|email_address|emailaddress|em|phone|phone_number|phonenumber|ph|"
    r"street|street_address|address1|address2|address_line_?1|address_line_?2|"
    r"first_name|firstname|full_name|fullname|fn|last_name|lastname|ln|user_city|ct|"
    r"user_region|st|postal_code|postalcode|zip|zp|external_id|user_id_value|"
    r"user_data|userprovideddata|user_provided_data|user_data_value|raw_user_data)$",
    re.IGNORECASE,
)
_EMAIL_VALUE = re.compile(r"(?<![\w.-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
_PHONE_VALUE = re.compile(r"(?<!\d)\+?\d(?:[\s().-]*\d){7,14}(?!\d)")
_AUTHORIZATION_VALUE = re.compile(
    r"(?:\b(?:Proxy[-_]?)?Authorization[\"']?\s*:\s*[\"']?(?:Bearer|Basic)\s+[^\s;,\"']+|"
    r"^\s*(?:Bearer|Basic)\s+\S{8,}\s*$)",
    re.IGNORECASE,
)
# Classify captured labels with the same key rules as native structured fields.
_ASSIGNMENT = re.compile(
    r"(?P<label>[A-Za-z_$][A-Za-z0-9_$ .-]{0,100})[\"']?\s*[:=]\s*"
    r"(?P<value>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^\s;,{}]+)"
)
_CREDENTIAL_FORMAT = re.compile(
    r"(?:\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9_-]{8,}\b|"
    r"\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{16,}\b|"
    r"\bxox[baprs]-[A-Za-z0-9-]{12,}\b|"
    r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]{8,}\b)"
)
_PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")
_URL_VALUE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_GTM_REFERENCE = re.compile(r"^\{\{[^{}]+\}\}$")
_GTM_REFERENCES = re.compile(r"\{\{([^{}]+)\}\}")
_SECRET_REFERENCE = re.compile(
    r"^(?:vault|secret|keyring)://[A-Za-z0-9][A-Za-z0-9._/@:-]{0,254}$",
    re.IGNORECASE,
)
_SAFE_METADATA_KEYS = {"secret_comparison", "secret_fields", "secret_state"}
_DESCRIPTOR_METADATA_KEYS = {
    "source",
    "source_path",
    "provenance",
    "source_shape",
    "destination_shape",
    "variable_reference",
    "secret_reference",
    "key_path",
    "parameter",
    "field_name",
    "missing_behavior",
}
_ROW_NAMES = {"parameter", "name", "key", "field_name", "header_name", "param_name"}
_ROW_VALUES = {
    "parameter_value",
    "value",
    "default_value",
    "header_value",
    "param_value",
    "field_value",
}
_CATEGORIES = {"credential", "pii", "declared-sensitive", "unknown"}
_DETECTORS = {
    "credential-key",
    "credential-private-field",
    "pii-key",
    "credential-row",
    "pii-row",
    "credential-variable-name",
    "pii-variable-name",
    "credential-variable-reference",
    "pii-variable-reference",
    "credential-assignment",
    "authorization-literal",
    "credential-url",
    "credential-query",
    "webhook-url",
    "private-key",
    "credential-format",
    "email-literal",
    "phone-literal",
    "declared-secret-path",
    "pii-descriptor-value",
    "invalid-marker",
    "redacted-unknown",
}


def _normalize(key: str) -> str:
    key = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", key)
    key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    return re.sub(r"[^\w]+", "_", key).strip("_").casefold()


def _key_category(key: str) -> str | None:
    normalized = _normalize(key)
    if normalized in _SAFE_METADATA_KEYS:
        return None
    # Cookie attributes and native cookie controls are ordinary configuration.
    if normalized in {"cookie", "set_cookie", "proxy_authorization"} or _SECRET_KEY.search(
        normalized
    ):
        return "credential"
    if _PII_KEY.fullmatch(normalized):
        return "pii"
    return None


def _private_hint(key: str) -> bool:
    normalized = _normalize(key)
    return normalized in {"cookie", "set_cookie"} or bool(_PRIVATE_FIELD.search(normalized))


def _field_reason(key: str, kind: str) -> tuple[str, str] | None:
    category = _key_category(key)
    if not category:
        return None
    detector = (
        "credential-private-field"
        if category == "credential" and _private_hint(key)
        else f"{category}-{kind}"
    )
    return category, detector


class SecretProvider(Protocol):
    """Ephemeral input interface; resolved values must never enter a run artifact."""

    def resolve(self, reference: str) -> str: ...


class SecretResolutionError(ValueError):
    """Raised when a redacted mutation field has no secure ephemeral value."""


def _valid_evidence(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"category", "detector"}
        and isinstance(value.get("category"), str)
        and value["category"] in _CATEGORIES
        and isinstance(value.get("detector"), str)
        and value["detector"] in _DETECTORS
    )


def redacted_marker(
    *, reference: str | None = None, category: str | None = None, detector: str | None = None
) -> dict[str, Any]:
    marker: dict[str, Any] = {"secret_state": REDACTED_STATE}
    if reference:
        reference = reference.strip()
        if not _SECRET_REFERENCE.fullmatch(reference):
            raise SecretResolutionError(
                "secret marker reference must be an opaque vault://, secret://, or keyring:// identifier"
            )
        marker["reference"] = reference
    if category is not None or detector is not None:
        evidence = {"category": category, "detector": detector}
        if not _valid_evidence(evidence):
            raise SecretResolutionError(
                "redaction evidence must use known category and detector codes"
            )
        marker["redaction"] = evidence
    return marker


def is_redacted(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) <= {"secret_state", "reference", "redaction"}
        and value.get("secret_state") == REDACTED_STATE
        and (
            "reference" not in value
            or isinstance(value["reference"], str)
            and bool(_SECRET_REFERENCE.fullmatch(value["reference"].strip()))
        )
        and ("redaction" not in value or _valid_evidence(value["redaction"]))
    )


def _literal_finding(value: str, *, declared_public: bool = False) -> tuple[str, str] | None:
    if _PRIVATE_KEY.search(value):
        return "credential", "private-key"
    if _CREDENTIAL_FORMAT.search(value):
        return "credential", "credential-format"
    if _AUTHORIZATION_VALUE.search(value):
        return "credential", "authorization-literal"
    # Query labels are classified separately. Do not mistake access_token= in a
    # public loader URL for a JavaScript credential assignment.
    urls = list(_URL_VALUE.finditer(value))
    assignments = _ASSIGNMENT.finditer(value) if ":" in value or "=" in value else ()
    for match in assignments:
        if any(url.start() <= match.start() < url.end() for url in urls):
            continue
        if _key_category(match["label"]) == "credential":
            return "credential", "credential-assignment"
    ambiguous_query = False
    for match in urls:
        try:
            parsed = urlsplit(match[0])
        except ValueError:
            continue
        if parsed.username is not None or parsed.password is not None:
            return "credential", "credential-url"
        for key, query_value in parse_qsl(parsed.query):
            # Inspect decoded values too; a public declaration cannot hide an
            # encoded secret, personal data, or another credential-bearing URL.
            nested = _literal_finding(query_value, declared_public=declared_public)
            if nested:
                return nested
            category = _key_category(key)
            if category == "pii":
                return "pii", "pii-key"
            if category == "credential" or key.casefold() == "key":
                ambiguous_query = True
        if (
            (parsed.hostname or "").casefold().startswith("hooks.slack.")
            and re.search(r"/services/[^/]+/[^/]+/[^/]+", parsed.path)
        ) or (
            re.fullmatch(r"(?:[^.]+\.)?discord(?:app)?\.(?:com|test)", parsed.hostname or "", re.I)
            and re.search(r"/api(?:/v\d+)?/webhooks/[^/]+/[^/]+", parsed.path)
        ):
            return "credential", "webhook-url"
    if "@" in value and _EMAIL_VALUE.search(value):
        return "pii", "email-literal"
    stripped = value.strip()
    if (
        sum(character.isdigit() for character in stripped) >= 9
        and (
            stripped.startswith("+")
            or any(ch in stripped for ch in " ().-")
            or bool(re.fullmatch(r"0\d{9}", stripped))
        )
        and _PHONE_VALUE.fullmatch(stripped)
    ):
        return "pii", "phone-literal"
    if ambiguous_query and not declared_public:
        return "credential", "credential-query"
    return None


def _inspected_template_scan_source(value: str) -> str:
    """Classify only reviewed test emails and a static injectScript cache-key name.

    Caller binds exact full source bytes to inspected provenance. Values stay intact
    for credential-format/Authorization/private-key detection; persisted code is untouched.
    """
    sections = re.split(r"(?m)^(___[A-Z_]+___)[ \t\r]*$", value)
    headers = sections[1::2]
    if len(headers) != len(set(headers)):
        return value
    if "___TESTS___" in headers:
        index = sections.index("___TESTS___") + 1
        sections[index] = _EMAIL_VALUE.sub("fixture-email", sections[index])
        # A test mock copying a symbol is not a literal credential. Quoted values,
        # Authorization strings and actual credential formats still run through detection.
        sections[index] = _ASSIGNMENT.sub(
            lambda match: (
                match[0].replace(match["label"], "fixtureReference", 1)
                if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", match["value"])
                else match[0]
            ),
            sections[index],
        )
    section = "___SANDBOXED_JS_FOR_WEB_TEMPLATE___"
    if section in headers:
        index = sections.index(section) + 1
        code = sections[index]
        if re.search(r"\bconst injectScript = require\('injectScript'\);", code):
            for match in list(
                re.finditer(
                    r"(?m)^const ([A-Za-z_$][A-Za-z0-9_$]*) = (['\"][A-Za-z0-9_-]+['\"]);[ \t\r]*$",
                    code,
                )
            ):
                name = match[1]
                if (
                    _key_category(name) == "credential"
                    and not _private_hint(name)
                    and len(re.findall(r"\b" + re.escape(name) + r"\b", code)) == 2
                    and re.search(
                        r"(?m)^injectScript\([^\n]*,\s*" + re.escape(name) + r"\);[ \t\r]*$", code
                    )
                ):
                    code = code.replace(match[0], match[0].replace(name, "scriptCacheKey", 1), 1)
            sections[index] = code
    return "".join(sections)


def _is_safe_reference(value: Any) -> bool:
    if is_redacted(value):
        return True
    if isinstance(value, str):
        return bool(_GTM_REFERENCE.fullmatch(value.strip()))
    if isinstance(value, dict):
        if set(value) == {"variable_reference"}:
            return isinstance(value["variable_reference"], str) and bool(
                value["variable_reference"].strip()
            )
        if set(value) == {"secret_reference"}:
            return isinstance(value["secret_reference"], str) and bool(
                _SECRET_REFERENCE.fullmatch(value["secret_reference"].strip())
            )
    return False


def _is_configuration_descriptor(value: Any) -> bool:
    return isinstance(value, dict) and bool(
        set(value) & (_DESCRIPTOR_METADATA_KEYS - {"secret_reference"})
    )


def _references(value: Any) -> set[str]:
    if isinstance(value, str):
        return {match.strip() for match in _GTM_REFERENCES.findall(value)}
    if isinstance(value, dict):
        output = set()
        for key, child in value.items():
            output.update(_references(child))
            if (
                key == "variable_reference"
                and isinstance(child, str)
                and not _GTM_REFERENCE.fullmatch(child.strip())
            ):
                output.add(child.strip())
        return output
    if isinstance(value, list):
        return set().union(*(_references(child) for child in value)) if value else set()
    return set()


def _variable_outputs(value: dict, path: str) -> set[str]:
    """Native literal-output slots, leaving LUT inputs, flags and DLV paths intact."""
    outputs: set[str] = set()
    kind = value.get("type")
    if kind not in {"c", "smm", "remm", "jsm"}:
        return outputs
    output_keys = (
        {"value"} if kind == "c" else {"javascript"} if kind == "jsm" else {"default_value"}
    )
    for key in value:
        if _normalize(key) in output_keys:
            outputs.add(f"{path}.{key}")
    parameters = value.get("parameter", [])
    if not isinstance(parameters, list):
        return outputs
    for index, parameter in enumerate(parameters):
        if not isinstance(parameter, dict):
            continue
        parameter_path = f"{path}.parameter[{index}]"
        key = _normalize(str(parameter.get("key", "")))
        if key in output_keys and "value" in parameter:
            outputs.add(f"{parameter_path}.value")
        if kind in {"smm", "remm"} and key == "map":
            rows = parameter.get("list", [])
            for row_index, row in enumerate(rows if isinstance(rows, list) else []):
                if not isinstance(row, dict):
                    continue
                fields = row.get("map", [])
                for field_index, field in enumerate(fields if isinstance(fields, list) else []):
                    if (
                        isinstance(field, dict)
                        and field.get("key") in {"value", "output"}
                        and "value" in field
                    ):
                        outputs.add(f"{parameter_path}.list[{row_index}].map[{field_index}].value")
    return outputs


# Cache only fingerprints and detector metadata, never scanned literals. The complete
# input and every external context participate; cross-object taint is still resolved
# by the full scanner on every miss. Bounded for long-lived MCP workers.
_SCAN_CACHE: OrderedDict[bytes, tuple[list[dict[str, str]], set[str]]] = OrderedDict()
_SCAN_CACHE_LOCK = Lock()


def _scan(value: Any, **context: Any) -> tuple[list[dict[str, str]], set[str]]:
    encoded = json.dumps(
        [
            value,
            {key: sorted(item) if isinstance(item, set) else item for key, item in context.items()},
        ],
        sort_keys=False,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    fingerprint = hashlib.sha256(encoded).digest()
    with _SCAN_CACHE_LOCK:
        cached = _SCAN_CACHE.get(fingerprint)
        if cached is not None:
            _SCAN_CACHE.move_to_end(fingerprint)
    if cached is not None:
        return deepcopy(cached)
    result = _scan_uncached(value, **context)
    # Avoid retaining exceptionally large reports in the cache.
    if len(result[0]) + len(result[1]) <= 1000:
        with _SCAN_CACHE_LOCK:
            _SCAN_CACHE[fingerprint] = deepcopy(result)
            if len(_SCAN_CACHE) > 256:
                _SCAN_CACHE.popitem(last=False)
    return result


def _scan_uncached(
    value: Any,
    *,
    path: str,
    exact_secret_paths: set[str],
    public_identifier_paths: set[str],
    secret_variable_names: set[str],
    protected_descriptor: bool,
    include_redacted: bool,
) -> tuple[list[dict[str, str]], set[str]]:
    # Scope prevents a same-named variable in another target from becoming evidence.
    tainted: dict[tuple[tuple[str, ...], str], str] = {}
    private_tainted: set[tuple[tuple[str, ...], str]] = set()
    all_referenced: set[str] = set(secret_variable_names)
    while True:
        findings: dict[str, dict[str, str]] = {}
        discovered: dict[tuple[tuple[str, ...], str], str] = {}
        discovered_private: set[tuple[tuple[str, ...], str]] = set()

        def walk(
            item: Any,
            here: str,
            owner: str,
            scope: tuple[str, ...],
            owner_name: str,
            forced: dict[str, tuple[str, str]],
            descriptor: bool = False,
            inherited: tuple[str, str] | None = None,
        ) -> None:
            def add(category: str, detector: str) -> None:
                findings[here] = {
                    "path": here,
                    "object_path": owner,
                    "category": category,
                    "detector": detector,
                }

            if is_redacted(item):
                if include_redacted:
                    evidence = item.get(
                        "redaction", {"category": "unknown", "detector": "redacted-unknown"}
                    )
                    add(evidence["category"], evidence["detector"])
                return
            if isinstance(item, dict) and item.get("secret_state") == REDACTED_STATE:
                add("declared-sensitive", "invalid-marker")
                return
            if isinstance(item, dict):
                own_scope = list(scope)
                for index, aliases in enumerate(
                    (
                        ("target_id",),
                        ("accountId", "account_id"),
                        ("containerId", "container_id"),
                        ("workspaceId", "workspace_id"),
                    )
                ):
                    for key in aliases:
                        if isinstance(item.get(key), (str, int)):
                            own_scope[index] = str(item[key])
                            break
                scope = tuple(own_scope)
                if isinstance(item.get("name"), str) and (
                    "type" in item or "resource_family" in item or "object_type" in item
                ):
                    owner, owner_name = here, item["name"]
                if item.get("type") in {"c", "smm", "remm", "jsm"}:
                    category = _key_category(owner_name) or tainted.get((scope, owner_name))
                    private = (
                        _private_hint(owner_name)
                        or (scope, owner_name) in private_tainted
                        or owner_name in secret_variable_names
                    )
                    if private:
                        category = "credential"
                    if category:
                        source = "name" if _key_category(owner_name) else "reference"
                        detector = (
                            "credential-private-field"
                            if private
                            else f"{category}-variable-{source}"
                        )
                        forced = {
                            **forced,
                            **{p: (category, detector) for p in _variable_outputs(item, here)},
                        }
            reason = forced.get(here) or inherited
            if here in exact_secret_paths:
                reason = ("declared-sensitive", "declared-secret-path")
            scan_item = item
            if (
                isinstance(item, str)
                and here.endswith(".templateData")
                and here in public_identifier_paths
            ):
                # Exact inspected source provenance authorizes non-operational test examples
                # only. Never alter retained source bytes or skip credential detectors.
                scan_item = _inspected_template_scan_source(item)
            literal = (
                _literal_finding(scan_item, declared_public=here in public_identifier_paths)
                if isinstance(item, str) and not _is_safe_reference(item)
                else None
            )
            if reason:
                # Only ambiguity from an inspected credential-shaped name/key is exemptible.
                if (
                    here in public_identifier_paths
                    and reason[0] == "credential"
                    and reason[1]
                    in {
                        "credential-key",
                        "credential-row",
                        "credential-variable-name",
                        "credential-variable-reference",
                    }
                ):
                    reason = None
                else:
                    for name in _references(item):
                        discovered[(scope, name)] = reason[0]
                        if reason[1] in {"credential-private-field", "declared-secret-path"}:
                            discovered_private.add((scope, name))
                        all_referenced.add(name)
            if literal or (reason and item not in (None, "") and not _is_safe_reference(item)):
                add(*(literal or reason))
                return
            if isinstance(item, dict):
                declared = item.get("secret_fields")
                next_forced = dict(forced)
                if isinstance(declared, list):
                    next_forced.update(
                        {
                            f"{here}.{field}": ("declared-sensitive", "declared-secret-path")
                            for field in declared
                            if isinstance(field, str) and field.strip()
                        }
                    )
                row_name = next(
                    (
                        item[key]
                        for key in (
                            "key",
                            "name",
                            "parameter",
                            "field_name",
                            "fieldName",
                            "paramName",
                            "headerName",
                        )
                        if isinstance(item.get(key), str)
                    ),
                    "",
                )
                row_category = _key_category(row_name)
                for key, child in item.items():
                    category = _key_category(key)
                    child_descriptor = category == "pii" and _is_configuration_descriptor(child)
                    child_reason = None
                    if category and not child_descriptor:
                        child_reason = _field_reason(key, "key")
                    elif row_category and _normalize(key) in _ROW_VALUES:
                        child_reason = _field_reason(row_name, "row")
                    elif descriptor and key not in _DESCRIPTOR_METADATA_KEYS:
                        child_reason = ("pii", "pii-descriptor-value")
                    walk(
                        child,
                        f"{here}.{key}",
                        owner,
                        scope,
                        owner_name,
                        next_forced,
                        child_descriptor,
                        child_reason,
                    )
            elif isinstance(item, list):
                # GTM Parameter map: semantic name and actual value are sibling entries.
                row_reason = next(
                    (
                        _field_reason(str(entry.get("value", entry.get("defaultValue", ""))), "row")
                        for entry in item
                        if isinstance(entry, dict)
                        and _normalize(str(entry.get("key", ""))) in _ROW_NAMES
                        and _key_category(str(entry.get("value", entry.get("defaultValue", ""))))
                    ),
                    None,
                )
                next_forced = dict(forced)
                if row_reason:
                    for index, entry in enumerate(item):
                        if (
                            isinstance(entry, dict)
                            and _normalize(str(entry.get("key", ""))) in _ROW_VALUES
                        ):
                            for field in ("value", "defaultValue"):
                                if field in entry:
                                    next_forced[f"{here}[{index}].{field}"] = row_reason
                for index, child in enumerate(item):
                    walk(
                        child, f"{here}[{index}]", owner, scope, owner_name, next_forced, descriptor
                    )

        walk(value, path, path, ("", "", "", ""), "", {}, protected_descriptor)
        added = {key: category for key, category in discovered.items() if key not in tainted}
        new_private = discovered_private - private_tainted
        if not added and not new_private:
            return [findings[key] for key in sorted(findings)], all_referenced
        tainted.update(added)
        private_tainted.update(new_private)


def sensitive_findings(
    value: Any,
    *,
    path: str = "$",
    exact_secret_paths: set[str] | None = None,
    protected_descriptor: bool = False,
    public_identifier_paths: set[str] | None = None,
    secret_variable_names: set[str] | None = None,
    include_redacted: bool = False,
) -> list[dict[str, str]]:
    """Return only paths and fixed detector codes, never a sensitive literal.

    Public paths must come from separately validated official/template evidence;
    declarations inside the scanned value do not authorize an exemption.
    """
    return _scan(
        value,
        path=path,
        exact_secret_paths=set(exact_secret_paths or ()),
        public_identifier_paths=set(public_identifier_paths or ()),
        secret_variable_names=set(secret_variable_names or ()),
        protected_descriptor=protected_descriptor,
        include_redacted=include_redacted,
    )[0]


def referenced_secret_variables(value: Any) -> set[str]:
    """Collect names from protected slots and close references in present native variables."""
    return _scan(
        value,
        path="$",
        exact_secret_paths=set(),
        public_identifier_paths=set(),
        secret_variable_names=set(),
        protected_descriptor=False,
        include_redacted=False,
    )[1]


def sensitive_paths(
    value: Any,
    *,
    path: str = "$",
    exact_secret_paths: set[str] | None = None,
    protected_descriptor: bool = False,
    public_identifier_paths: set[str] | None = None,
    secret_variable_names: set[str] | None = None,
) -> list[str]:
    """Return paths that still contain a literal credential or user value."""
    return [
        item["path"]
        for item in sensitive_findings(
            value,
            path=path,
            exact_secret_paths=exact_secret_paths,
            protected_descriptor=protected_descriptor,
            public_identifier_paths=public_identifier_paths,
            secret_variable_names=secret_variable_names,
        )
    ]


def exposure_findings(value: Any) -> list[dict[str, str]]:
    """Locate typed marker evidence, reporting untyped markers as unknown."""
    return sensitive_findings(value, include_redacted=True)


def redact_for_persistence(
    value: Any,
    *,
    exact_secret_paths: set[str] | None = None,
    path: str = "$",
    protected_descriptor: bool = False,
    public_identifier_paths: set[str] | None = None,
    secret_variable_names: set[str] | None = None,
) -> Any:
    """Return a deep redacted copy; detection and write gating use one authority."""
    findings = {
        item["path"]: item
        for item in sensitive_findings(
            value,
            path=path,
            exact_secret_paths=exact_secret_paths,
            protected_descriptor=protected_descriptor,
            public_identifier_paths=public_identifier_paths,
            secret_variable_names=secret_variable_names,
        )
    }

    def visit(item: Any, here: str) -> Any:
        if is_redacted(item):
            return deepcopy(item)
        if here in findings:
            finding = findings[here]
            if isinstance(item, dict) and item.get("secret_state") == REDACTED_STATE:
                # Strip injected metadata/raw fields; keep only independently valid references.
                reference = item.get("reference")
                return redacted_marker(
                    reference=reference
                    if isinstance(reference, str) and _SECRET_REFERENCE.fullmatch(reference.strip())
                    else None
                )
            return redacted_marker(category=finding["category"], detector=finding["detector"])
        if isinstance(item, dict):
            return {key: visit(child, f"{here}.{key}") for key, child in item.items()}
        if isinstance(item, list):
            return [visit(child, f"{here}[{index}]") for index, child in enumerate(item)]
        return deepcopy(item)

    return visit(value, path)


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
    """Resolve referenced markers in memory; callers must never persist returned values."""
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
    """Scrub ephemeral secrets and recognized formats before persisting an error."""
    output = value
    for secret in sorted(sensitive_values, key=len, reverse=True):
        output = output.replace(secret, "[REDACTED]")
    # Exception strings have no reliable field structure; suppress affected text.
    return "[REDACTED]" if _literal_finding(output) else output
