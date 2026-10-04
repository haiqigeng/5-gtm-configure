#!/usr/bin/env python3
"""Native GTM MCP adapter for the existing configuration runtime."""

from __future__ import annotations

import math
import re
from copy import deepcopy
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable

from action_contract import validate_native_authoring
from adapter_support import (
    AdapterExecutionError,
    AmbiguousWriteError,
    AuthenticationError,
    RateLimitError,
    collect_paginated,
)
from diff_object_graph import (
    BUILT_IN_TRIGGER_IDS,
    ID_FIELDS,
    REFERENCE_FIELDS,
    ROOT_METADATA_KEYS,
    SEQUENCING_KEYS,
)
from public_identifiers import public_identifier_paths
from strict_json import loads_strict

FAMILIES = {
    "tag": ("gtm_tag", "tagId"),
    "trigger": ("gtm_trigger", "triggerId"),
    "variable": ("gtm_variable", "variableId"),
    "folder": ("gtm_folder", "folderId"),
    "client": ("gtm_client", "clientId"),
    "transformation": ("gtm_transformation", "transformationId"),
    "template": ("gtm_template", "templateId"),
    "zone": ("gtm_zone", "zoneId"),
}


def _retry_after(response: dict, details: Any, error: Any) -> float | None:
    for source in (error, details, response):
        if not isinstance(source, dict):
            continue
        headers = source.get("headers", {})
        values = [source.get("retry_after_seconds"), source.get("retryAfter")]
        if isinstance(headers, dict):
            values.extend(
                value for key, value in headers.items() if key.casefold() == "retry-after"
            )
        for value in values:
            if value is None or isinstance(value, bool):
                continue
            try:
                seconds = float(value)
            except (TypeError, ValueError):
                try:
                    seconds = (
                        parsedate_to_datetime(str(value)) - datetime.now(timezone.utc)
                    ).total_seconds()
                except (TypeError, ValueError, OverflowError):
                    continue
            if math.isfinite(seconds) and seconds >= 0:
                return seconds
    return None


def unwrap(response: Any, *, mutation: bool = False) -> Any:
    if not isinstance(response, dict):
        raise AdapterExecutionError("MCP result must be an object")
    if response.get("isError"):
        details = response.get("structuredContent")
        if details is None:
            texts = [
                item.get("text")
                for item in response.get("content", [])
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            if len(texts) == 1:
                try:
                    details = loads_strict(texts[0])
                except (ValueError, TypeError):
                    pass
        error = details.get("error") if isinstance(details, dict) else None
        code = error.get("code") if isinstance(error, dict) else None
        # Only structured endpoint rejection codes establish that a write was rejected.
        # Arbitrary prose, MCP transport errors and server failures remain ambiguous.
        if type(code) is int and code == 401:
            raise AuthenticationError("MCP endpoint rejected authentication (401)")
        reasons = error.get("errors") if isinstance(error, dict) else None
        if (
            type(code) is int
            and code == 403
            and isinstance(reasons, list)
            and reasons
            and all(
                isinstance(item, dict)
                and item.get("reason") in {"rateLimitExceeded", "userRateLimitExceeded"}
                for item in reasons
            )
        ):
            # A full GTM sliding window, through the existing bounded retry policy.
            raise RateLimitError(
                "MCP endpoint rejected the request (403 quota)",
                retry_after_seconds=_retry_after(response, details, error),
            )
        if type(code) is int and code == 429:
            raise RateLimitError(
                "MCP endpoint rejected the request (429)",
                retry_after_seconds=_retry_after(response, details, error),
            )
        if type(code) is int and code in {400, 403, 404, 409, 422}:
            raise AdapterExecutionError("MCP endpoint rejected the request", code=f"http_{code}")
        if mutation:
            raise AmbiguousWriteError("MCP write outcome is unknown; read back before retry")
        raise AdapterExecutionError("MCP read failed", code="read_failed")
    if "structuredContent" in response:
        return response["structuredContent"]
    if "content" in response:
        texts = [item["text"] for item in response["content"] if item.get("type") == "text"]
        if len(texts) != 1:
            raise AdapterExecutionError("Expected one JSON MCP content block")
        return loads_strict(texts[0])
    return response


def select(value: Any, path: list[str]) -> Any:
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise AdapterExecutionError("MCP response differs from discovered response path")
        value = value[key]
    return value


class McpTargetAdapter:
    """Map discovered MCP schemas to the runtime protocol without client-specific code.

    Profile response paths and pagination must come from inspected tool responses.
    Intentions use native GTM fields; no invented aliases or lossy projection is applied.
    """

    def __init__(self, target: dict, profile: dict, call: Callable[[str, dict], dict]):
        if not isinstance(profile, dict) or not isinstance(profile.get("tool_prefix"), str):
            raise AdapterExecutionError(
                "MCP profile needs the discovered tool prefix (empty for unprefixed server tools)"
            )
        for key in ("workspace_path", "container_path", "status_path"):
            if not isinstance(profile.get(key), list) or any(
                not isinstance(item, str) for item in profile[key]
            ):
                raise AdapterExecutionError(
                    "MCP profile needs discovered workspace/container/status paths"
                )
        families = profile.get("families")
        if "sequencing_reference" in profile and profile["sequencing_reference"] not in {
            "name",
            "tagId",
        }:
            raise AdapterExecutionError("Invalid inspected sequencing reference representation")
        if not isinstance(families, dict) or not families or set(families) - set(FAMILIES):
            raise AdapterExecutionError(
                "MCP profile contains missing or unsupported resource families"
            )
        for config in families.values():
            if (
                not isinstance(config, dict)
                or not isinstance(config.get("actions"), list)
                or not config["actions"]
                or set(config["actions"]) - {"get", "list", "create", "update", "remove"}
            ):
                raise AdapterExecutionError("MCP profile needs discovered supported family actions")
            if (
                type(config.get("page_size")) is not int
                or config["page_size"] < 1
                or type(config.get("first_page")) is not int
                or config["first_page"] not in (0, 1)
            ):
                raise AdapterExecutionError("Invalid discovered pagination configuration")
            for key in (
                "list_path",
                "object_path",
                *(["has_more_path"] if "has_more_path" in config else []),
            ):
                if not isinstance(config.get(key), list) or any(
                    not isinstance(item, str) for item in config[key]
                ):
                    raise AdapterExecutionError(
                        "MCP profile needs discovered family response paths"
                    )
        self._target = deepcopy(target)
        self._profile = deepcopy(profile)
        self._bound_call = call
        self._identity: dict[str, str] | None = None
        self.cache: dict[str, list[dict]] = {}
        self.complete_families: set[str] = set()
        self.known_ids: dict[str, str] = {}
        self.fresh_reads: dict[str, dict] = {}

    @property
    def target(self) -> dict:
        return deepcopy(self._target)

    @property
    def profile(self) -> dict:
        return deepcopy(self._profile)

    @property
    def call(self) -> Callable[[str, dict], dict]:
        return self._bound_call

    def _call(
        self, tool: str, action: str, *, public_paths: set[str] | None = None, **extra: Any
    ) -> Any:
        if action not in {"get", "list", "create", "update", "remove", "getStatus"}:
            raise AdapterExecutionError("Unsupported MCP action")
        arguments = {
            "accountId": self.target["account_id"],
            "containerId": self.target["container_id"],
            "action": action,
        }
        if tool != "gtm_container":
            arguments["workspaceId"] = self.target["workspace_id"]
        if set(extra) & {"accountId", "containerId", "workspaceId", "action"}:
            raise AdapterExecutionError("Cannot override bound MCP addressing")
        arguments.update(extra)
        if public_paths:
            response = self.call(
                self.profile["tool_prefix"] + tool,
                arguments,
                public_identifier_paths=public_paths,
            )
        else:
            response = self.call(self.profile["tool_prefix"] + tool, arguments)
        try:
            return unwrap(response, mutation=action in {"create", "update", "remove"})
        except AdapterExecutionError as exc:
            if action in {"create", "update", "remove"} and exc.code == "adapter_error":
                raise AmbiguousWriteError(
                    "Invalid mutation response; read back before retry"
                ) from exc
            raise
        except Exception as exc:
            if action in {"create", "update", "remove"}:
                raise AmbiguousWriteError(
                    "Invalid mutation response; read back before retry"
                ) from exc
            raise

    def identity(self) -> dict[str, str]:
        # Every request remains explicitly addressed to this immutable native target.
        # A new adapter (including reconnect/resume) authenticates again. Reads/writes
        # still enforce current server authorization and strict response scope.
        if self._identity is not None:
            return deepcopy(self._identity)
        workspace = select(self._call("gtm_workspace", "get"), self.profile["workspace_path"])
        container = select(self._call("gtm_container", "get"), self.profile["container_path"])
        usage = container.get("usageContext")
        if usage not in (["web"], ["server"]):
            raise AdapterExecutionError("Unsupported authenticated container usageContext")
        if any(
            str(workspace.get(key)) != str(container.get(key))
            for key in ("accountId", "containerId")
        ):
            raise AdapterExecutionError("Workspace and container identities disagree")
        observed = {
            "account_id": str(workspace["accountId"]),
            "container_id": str(workspace["containerId"]),
            "workspace_id": str(workspace["workspaceId"]),
            "container_type": usage[0],
        }
        if observed != {key: str(self._target[key]) for key in observed}:
            raise AdapterExecutionError("Authenticated MCP identity differs from bound target")
        self._identity = observed
        return deepcopy(observed)

    def capabilities(self) -> dict:
        return {
            family: {
                action: action in config["actions"]
                for action in ("get", "list", "create", "update", "remove")
            }
            for family, config in self.profile["families"].items()
            if family in FAMILIES
        }

    def list_resource_page(self, resource_family: str, cursor: str | None) -> dict:
        config = self.profile["families"].get(resource_family)
        if config is None or "list" not in config["actions"]:
            raise AdapterExecutionError("Required resource list capability is unavailable")
        tool, _ = FAMILIES[resource_family]
        if (
            type(config["page_size"]) is not int
            or config["page_size"] < 1
            or config["first_page"] not in (0, 1)
        ):
            raise AdapterExecutionError("Invalid discovered pagination configuration")
        page = int(cursor) if cursor is not None else config["first_page"]
        result = self._call(tool, "list", page=page, itemsPerPage=config["page_size"])
        items = select(result, config["list_path"])
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise AdapterExecutionError("Discovered list path must contain objects")
        if len(items) > config["page_size"]:
            raise AdapterExecutionError("MCP ignored discovered page size; exhaustion is unproved")
        for item in items:
            self._check_scope(item)
        if cursor is None:
            self.complete_families.discard(resource_family)
            self.cache[resource_family] = []
        self.cache[resource_family].extend(deepcopy(items))
        # Honor an explicit discovered continuation flag, including short pages.
        if "has_more_path" in config:
            has_more = select(result, config["has_more_path"])
            if type(has_more) is not bool or (has_more and not items):
                raise AdapterExecutionError("Invalid pagination continuation evidence")
        else:
            # Use this mode only after discovering short-page exhaustion semantics.
            has_more = len(items) == config["page_size"]
        if not has_more:
            self.complete_families.add(resource_family)
        return {
            "items": items,
            "next_cursor": str(page + 1) if has_more else None,
        }

    def list_workspace_changes_page(self, cursor: str | None) -> dict:
        if cursor is not None:
            raise AdapterExecutionError("getStatus is not paginated")
        status = select(self._call("gtm_workspace", "getStatus"), self.profile["status_path"])
        if status.get("mergeConflict"):
            raise AdapterExecutionError("Workspace has unresolved merge conflicts")
        return {"items": status.get("workspaceChange", []), "next_cursor": None}

    def _check_scope(self, raw: dict) -> None:
        fields = {
            "accountId": "account_id",
            "containerId": "container_id",
            "workspaceId": "workspace_id",
        }
        for field, target_field in fields.items():
            if field in raw and str(raw[field]) != str(self._target[target_field]):
                raise AdapterExecutionError("MCP object belongs to another target")
        prefix = (
            "accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/".format(
                **self._target
            )
        )
        path = raw.get("path")
        scoped_path = (
            isinstance(path, str)
            and re.fullmatch(
                re.escape(prefix)
                + r"(?:tags|triggers|variables|folders|clients|transformations|templates|zones)/[^/]+",
                path,
            )
            is not None
        )
        if scoped_path:
            collection, identifier = path[len(prefix) :].split("/")
            family = collection.removesuffix("s")
            id_field = FAMILIES[family][1]
            if id_field in raw and str(raw[id_field]) != identifier:
                raise AdapterExecutionError("MCP object ID differs from its native path")
        if "path" in raw and not scoped_path:
            raise AdapterExecutionError("MCP object path belongs to another target or is invalid")
        if not (set(fields) <= set(raw) or scoped_path):
            raise AdapterExecutionError("MCP object lacks complete native target scope")

    def _find(self, operation: dict) -> dict | None:
        family = operation["resource_family"]
        tool, id_field = FAMILIES[family]
        config = self.profile["families"][family]
        identifier = operation.get("object_id") or self.known_ids.get(operation["object_key"])
        if (
            not identifier
            and operation["action"] != "remove"
            and not (operation["action"] == "create" and operation.get("state") != "planned")
        ):
            # The complete baseline is only an ID hint; the following get still
            # verifies current contents and scope. Creates always prove absence.
            matches = [
                item for item in self.cache.get(family, []) if item.get("name") == operation["name"]
            ]
            if len(matches) > 1:
                raise AdapterExecutionError("Ambiguous GTM object identity")
            if matches:
                identifier = str(matches[0][id_field])
            elif operation["action"] == "create" and family in self.complete_families:
                return None
        # Listing by exact identity also gives authoritative absence after removal.
        if not identifier or operation["action"] == "remove":
            items = collect_paginated(lambda cursor: self.list_resource_page(family, cursor))
            matches = [
                item
                for item in items
                if (
                    str(item.get(id_field)) == identifier
                    if identifier
                    else item.get("name") == operation["name"]
                )
            ]
            if len(matches) > 1:
                raise AdapterExecutionError("Ambiguous GTM object identity")
            if not matches:
                return None
            identifier = str(matches[0][id_field])
        raw = select(self._call(tool, "get", **{id_field: identifier}), config["object_path"])
        if not isinstance(raw, dict) or str(raw.get(id_field)) != identifier:
            raise AdapterExecutionError("Readback object ID differs from requested object")
        self._check_scope(raw)
        self.known_ids[operation["object_key"]] = identifier
        self.fresh_reads[operation["object_key"]] = deepcopy(raw)
        return raw

    def read(self, operation: dict) -> dict | None:
        raw = self._find(operation)
        if raw is None:
            return None
        return self.observation(operation, raw)

    def observation(self, operation: dict, raw: dict) -> dict:
        """Attach only the transitive native reference closure to one observation."""
        # A resumed process has no in-memory baseline cache. Load native reference
        # families before capturing this observation, even when the run is verified.
        referenced = {
            next(family for family, (_, identifier) in FAMILIES.items() if identifier == id_field)
            for field, id_field in REFERENCE_FIELDS.items()
            if raw.get(field)
            and not (
                id_field == "triggerId"
                and isinstance(raw[field], list)
                and all(str(value) in BUILT_IN_TRIGGER_IDS for value in raw[field])
            )
        }
        if raw.get("setupTag") or raw.get("teardownTag"):
            referenced.add("tag")
        for family in sorted(referenced - self.complete_families):
            collect_paginated(lambda cursor, family=family: self.list_resource_page(family, cursor))
        context = []
        pending = [raw]
        seen = {
            (operation["resource_family"], str(raw.get(FAMILIES[operation["resource_family"]][1])))
        }
        while pending:
            body = pending.pop()
            names = set(re.findall(r"\{\{([^{}]+)\}\}", str(body)))
            ids = {}
            for field, identifier in REFERENCE_FIELDS.items():
                values = body.get(field, [])
                ids.setdefault(ID_FIELDS[identifier], set()).update(
                    str(v) for v in (values if isinstance(values, list) else [values])
                )
            sequencing = {
                str(row.get("tagName")) for field in SEQUENCING_KEYS for row in body.get(field, [])
            }
            for family, items in self.cache.items():
                identifier = FAMILIES[family][1]
                for item in items:
                    identity = (family, str(item.get(identifier)))
                    relevant = (
                        str(item.get(identifier)) in ids.get(family, set())
                        or family == "variable"
                        and item.get("name") in names
                        or family == "tag"
                        and (
                            item.get("name") in sequencing
                            or str(item.get(identifier)) in sequencing
                        )
                    )
                    if relevant and identity not in seen:
                        seen.add(identity)
                        context.append(
                            {**item, "target_id": operation["target_id"], "object_type": family}
                        )
                        pending.append(item)
        return {
            "objects": [
                {
                    **raw,
                    "target_id": operation["target_id"],
                    "object_type": operation["resource_family"],
                }
            ],
            "context_objects": context,
        }

    def _resolve_reference(
        self, value: Any, reference_id: str, *, allow_name: bool = False, as_name: bool = False
    ) -> str:
        if not isinstance(value, str) or not value:
            raise AdapterExecutionError("GTM reference must be a non-empty string")
        family = ID_FIELDS[reference_id]
        target = self.target["target_id"]
        if family == "trigger":
            for identifier in BUILT_IN_TRIGGER_IDS:
                if value in {
                    identifier,
                    f"trigger::builtin::{identifier}",
                    f"{target}::trigger::builtin::{identifier}",
                }:
                    return identifier
        if family not in self.complete_families:
            collect_paginated(lambda cursor: self.list_resource_page(family, cursor))
        matches = []
        for item in self.cache.get(family, []):
            aliases = {
                str(item.get(reference_id)),
                f"{family}::{item.get('name')}",
                f"{target}::{family}::{item.get('name')}",
            }
            if allow_name:
                aliases.add(item.get("name"))
            if value in aliases and item.get(reference_id):
                self._check_scope(item)
                matches.append(item)
        if len(matches) > 1:
            raise AdapterExecutionError("Ambiguous GTM reference")
        if matches:
            return str(matches[0]["name" if as_name else reference_id])
        raise AdapterExecutionError("Unresolved GTM reference")

    def _serialize_references(self, intended: dict) -> None:
        for field, reference_id in REFERENCE_FIELDS.items():
            if field in intended:
                value = intended[field]
                intended[field] = (
                    [self._resolve_reference(item, reference_id) for item in value]
                    if isinstance(value, list)
                    else self._resolve_reference(value, reference_id)
                )
        for field in SEQUENCING_KEYS:
            for row in intended.get(field, []):
                value = row["tagName"]
                representation = self.profile.get("sequencing_reference")
                if representation is None:
                    # Native values can be retained; private semantic keys require an
                    # inspected wire representation, not a guess from the field label.
                    if "::" in value:
                        raise AdapterExecutionError(
                            "Inspect sequencing_reference (name or tagId) before mutation"
                        )
                    self._resolve_reference(value, "tagId", allow_name=True)
                else:
                    row["tagName"] = self._resolve_reference(
                        value, "tagId", allow_name=True, as_name=representation == "name"
                    )

    def mutate(self, operation: dict) -> dict | None:
        family = operation["resource_family"]
        tool, id_field = FAMILIES[family]
        action = operation["action"]
        if action == "replace":
            raise AdapterExecutionError(
                "MCP replacement requires a dedicated adapter with recovery for both boundaries"
            )
        action = "update" if action in {"rename", "pause", "unpause"} else action
        if (
            action not in {"create", "update", "remove"}
            or action not in self.profile["families"][family]["actions"]
        ):
            raise AdapterExecutionError("Undiscovered mutation capability")
        arguments = {}
        if action != "create":
            arguments[id_field] = operation["object_id"]
            current = self.fresh_reads.pop(operation["object_key"], None)
            if current is None or str(current.get(id_field)) != str(operation["object_id"]):
                raise AdapterExecutionError(
                    "Mutation requires an immediately preceding scoped read"
                )
            fingerprint = current.get("fingerprint")
            if fingerprint:
                arguments["fingerprint"] = fingerprint
        if action != "remove":

            def invalid(message):
                raise AdapterExecutionError(message, code="invalid_native_shape")

            validate_native_authoring(family, operation["intended"], path="intended", fail=invalid)
            intended = {
                key: deepcopy(value)
                for key, value in operation["intended"].items()
                if key not in ROOT_METADATA_KEYS | {"target_id", "object_type"}
            }
            intended["name"] = operation.get("new_name", operation["name"])
            self._serialize_references(intended)
            arguments["createOrUpdateConfig"] = intended
        result = self._call(
            tool,
            action,
            public_paths=public_identifier_paths(arguments, records=[operation]),
            **arguments,
        )
        if action != "remove":
            try:
                raw = select(result, self.profile["families"][family]["object_path"])
                if (
                    not isinstance(raw, dict)
                    or not isinstance(raw.get(id_field), str)
                    or not raw[id_field]
                ):
                    raise AdapterExecutionError("Mutation response has no native object ID")
                self._check_scope(raw)
                if action != "create" and raw[id_field] != str(arguments[id_field]):
                    raise AdapterExecutionError("Mutation response object ID differs")
            except Exception as exc:
                raise AmbiguousWriteError(
                    "Invalid saved-object response; read back before retry"
                ) from exc
            self.known_ids[operation["object_key"]] = str(raw[id_field])
            self.cache.setdefault(family, [])[:] = [
                item
                for item in self.cache.get(family, [])
                if str(item.get(id_field)) != str(raw[id_field])
            ] + [deepcopy(raw)]
        return self.observation(operation, raw) if action != "remove" else None
