from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from gtm_configure.core.privacy import redacted_marker
from gtm_configure.domain.resources import required_baseline_families
from gtm_configure.runtime.adapter_protocol import atomic_write
from gtm_configure.runtime.engine import (
    AdapterExecutionError,
    RateLimitError,
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from gtm_configure.runtime.state import create_from_contract, load_document
from gtm_configure.runtime.verification import expected_graph

from support.contracts import (  # noqa: E402
    approve_mutations,
    valid_pipeline_contract,
    valid_server_contract,
    valid_web_contract,
    with_complete_baselines,
)

ROOT = Path(__file__).resolve().parents[2]


def capabilities(*families: str) -> dict:
    return {
        family: {
            "list": True,
            "get": True,
            "create": True,
            "update": True,
            "remove": True,
        }
        for family in families
    }


class FakeAdapter:
    def __init__(
        self,
        *,
        existing: set[str] | None = None,
        fail_names: set[str] | None = None,
        rate_limit_once: set[str] | None = None,
        read_overrides: dict[str, dict] | None = None,
    ) -> None:
        self.existing = set(existing or set())
        self.fail_names = set(fail_names or set())
        self.rate_limit_once = set(rate_limit_once or set())
        self.read_overrides = deepcopy(read_overrides or {})
        self.saved: dict[str, dict] = {}
        self.mutations: list[str] = []
        self.attempts: dict[str, int] = {}
        self.received: list[dict] = []
        self.observed_identity: dict[str, str] | None = None

    def bind_target(self, target: dict) -> None:
        self.observed_identity = {
            field: target[field]
            for field in ("account_id", "container_id", "workspace_id", "container_type")
        }

    def identity(self) -> dict[str, str]:
        if self.observed_identity is None:
            raise RuntimeError("fake adapter target is not bound")
        return deepcopy(self.observed_identity)

    def read(self, operation: dict) -> dict | None:
        name = operation["name"]
        if name in self.read_overrides:
            return deepcopy(self.read_overrides[name])
        if name in self.saved:
            return deepcopy(self.saved[name])
        if name in self.existing:
            if operation.get("pre_change") is not None:
                return {"name": operation["name"], **deepcopy(operation["pre_change"])}
            self.saved[name] = expected_graph(operation)
            if operation.get("object_id"):
                self.saved[name]["objects"][0][operation["resource_family"] + "Id"] = operation[
                    "object_id"
                ]
            return deepcopy(self.saved[name])
        return None

    def mutate(self, operation: dict) -> dict | None:
        name = operation["name"]
        self.received.append(deepcopy(operation))
        self.attempts[name] = self.attempts.get(name, 0) + 1
        if name in self.rate_limit_once and self.attempts[name] == 1:
            raise RateLimitError("retry later", retry_after_seconds=0)
        if name in self.fail_names:
            raise AdapterExecutionError("documented target rejection", code="target_rejected")
        self.mutations.append(name)
        self.saved[name] = expected_graph(operation)
        if operation.get("object_id"):
            self.saved[name]["objects"][0][operation["resource_family"] + "Id"] = operation[
                "object_id"
            ]
        return deepcopy(self.saved[name])

    def list_resource_page(self, resource_family: str, cursor: str | None) -> dict:
        if cursor is not None:
            raise AssertionError("fake adapter has only one baseline page")
        from gtm_configure.comparison.native import ID_FIELDS

        id_field = next(key for key, value in ID_FIELDS.items() if value == resource_family)
        items = []
        for name, graph in {**self.saved, **self.read_overrides}.items():
            for raw in graph.get("objects", []):
                if raw.get("object_type") == resource_family:
                    items.append({id_field: name, **deepcopy(raw)})
        return {"items": items, "next_cursor": None}

    def list_workspace_changes_page(self, cursor: str | None) -> dict:
        if cursor is not None:
            raise AssertionError("fake adapter has only one workspace-change page")
        return {"items": [], "next_cursor": None}


class StaticSecretProvider:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    def resolve(self, reference: str) -> str:
        return self.values[reference]


class CurrentAdapterRuntimeTestFixture(unittest.TestCase):
    def _execute(
        self,
        contract: dict,
        bindings: dict[str, tuple[FakeAdapter, dict, StaticSecretProvider | None]],
        **kwargs: object,
    ) -> tuple[dict, dict[str, FakeAdapter]]:
        approve_mutations(contract)
        run = create_from_contract(
            contract,
            run_id="RUN-ADAPTER",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
        run = with_complete_baselines(run)
        target_by_id = {item["target_id"]: item for item in run["run"]["targets"]}
        registry = TargetAdapterRegistry()
        adapters: dict[str, FakeAdapter] = {}
        for target_id, (adapter, matrix, provider) in bindings.items():
            adapter.bind_target(target_by_id[target_id])
            registry.register(
                target_by_id[target_id],
                adapter,
                matrix,
                secret_provider=provider,
            )
            adapters[target_id] = adapter
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.json"
            atomic_write(path, run)
            execute_ready_operations(
                path,
                registry,
                timestamp=lambda: "2026-08-18T00:00:01Z",
                sleep=kwargs.pop("sleep", lambda _: None),
                **kwargs,
            )
            return load_document(path), adapters


__all__ = [
    "CurrentAdapterRuntimeTestFixture",
    "FakeAdapter",
    "Path",
    "RateLimitError",
    "StaticSecretProvider",
    "TargetAdapterRegistry",
    "atomic_write",
    "capabilities",
    "create_from_contract",
    "deepcopy",
    "execute_ready_operations",
    "expected_graph",
    "json",
    "load_document",
    "redacted_marker",
    "required_baseline_families",
    "tempfile",
    "valid_pipeline_contract",
    "valid_server_contract",
    "valid_web_contract",
    "verify_idempotent_rerun",
    "with_complete_baselines",
]
