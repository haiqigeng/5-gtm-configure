from __future__ import annotations

import sys
import tempfile
import unittest
from collections import defaultdict, deque
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from adapter_runtime import (  # noqa: E402
    AdapterExecutionError,
    AmbiguousWriteError,
    AuthenticationError,
    RateLimitError,
    collect_paginated,
    execute_ready_operations,
)
from configuration_run import atomic_write, create_from_contract, load_document  # noqa: E402


def configuration_contract(object_count: int = 1) -> dict:
    requirement_id = "TP::Events::12::purchase"
    objects = []
    for index in range(1, object_count + 1):
        record = {
            "action": "create",
            "object_type": "tag" if index == object_count else "variable",
            "name": f"Object {index}",
            "requirement_ids": [requirement_id],
            "justification": "Implements the approved requirement.",
            "evidence": ["approved-input", "official-current", "container-confirmed"],
            "intended": {
                "object_type": "tag" if index == object_count else "variable",
                "name": f"Object {index}",
                "value": index,
            },
        }
        if index > 1:
            previous_type = "tag" if index - 1 == object_count else "variable"
            record["dependencies"] = [f"{previous_type}::Object {index - 1}"]
        objects.append(record)
    return {
        "schema_version": "5.0",
        "route": "analytics",
        "scope": {"included": [requirement_id], "reference_only": [], "excluded": []},
        "requirements": [
            {
                "id": requirement_id,
                "authority": {"grade": "approved-input", "locator": "Plan / row 12"},
                "event_name": "purchase",
                "source_event": "purchase",
            }
        ],
        "implementation": {
            "workspace": {
                "account_id": "1",
                "container_id": "2",
                "id": "3",
                "container_type": "web",
            },
            "objects": objects,
        },
        "evidence": [
            {
                "grade": "official-current",
                "locator": "Official schema",
                "url": "https://developers.google.com/example",
                "title": "Official schema",
                "access_date": "2026-08-01",
            },
            {"grade": "container-confirmed", "locator": "Workspace IDs"},
        ],
        "external_dependencies": [],
    }


def configuration_run(object_count: int = 1) -> dict:
    return create_from_contract(
        configuration_contract(object_count),
        run_id="RUN-ADAPTER",
        source_locator="Plan / Events",
        timestamp="2026-08-01T10:00:00Z",
    )


class FakeAdapter:
    def __init__(self, behaviors: dict[str, list[str]] | None = None) -> None:
        self.behaviors = {key: deque(values) for key, values in (behaviors or {}).items()}
        self.saved: dict[str, dict] = {}
        self.mutate_calls = defaultdict(int)
        self.page_calls: list[str | None] = []

    def list_page(self, cursor: str | None) -> dict:
        self.page_calls.append(cursor)
        if cursor is None:
            return {"items": [{"object_key": "variable::Existing"}], "next_cursor": "page-2"}
        return {"items": [{"object_key": "trigger::Existing"}], "next_cursor": None}

    def read(self, operation: dict) -> dict | None:
        return self.saved.get(operation["object_key"])

    def matches(self, operation: dict, saved: dict | None) -> bool:
        return saved is not None and saved.get("intended") == operation.get("intended")

    def mutate(self, operation: dict) -> dict | None:
        operation_id = operation["operation_id"]
        self.mutate_calls[operation_id] += 1
        behavior = self.behaviors.get(operation_id, deque(["success"]))
        outcome = behavior.popleft() if behavior else "success"
        if outcome == "rate-limit":
            raise RateLimitError("quota retry")
        if outcome == "auth":
            raise AuthenticationError("token expired")
        saved = {
            "intended": deepcopy(operation.get("intended")),
            "object_id": f"id-{operation_id}",
            "fingerprint": f"fp-{operation_id}",
        }
        if outcome == "ambiguous-saved":
            self.saved[operation["object_key"]] = saved
            raise AmbiguousWriteError("timeout after send")
        if outcome == "ambiguous-absent":
            raise AmbiguousWriteError("timeout before response")
        self.saved[operation["object_key"]] = saved
        return saved


class AdapterRuntimeTest(unittest.TestCase):
    def run_path(self, root: Path, count: int = 1) -> Path:
        path = root / "run.json"
        atomic_write(path, configuration_run(count))
        return path

    def test_collect_paginated_exhausts_every_page_and_bounds_rate_limits(self) -> None:
        calls = []

        def fetch(cursor: str | None) -> dict:
            calls.append(cursor)
            if len(calls) == 1:
                raise RateLimitError("retry")
            if cursor is None:
                return {"items": [{"id": "1"}], "next_cursor": "next"}
            return {"items": [{"id": "2"}], "next_cursor": None}

        self.assertEqual([item["id"] for item in collect_paginated(fetch)], ["1", "2"])
        self.assertEqual(calls, [None, None, "next"])

        with self.assertRaises(RateLimitError):
            collect_paginated(lambda _: (_ for _ in ()).throw(RateLimitError("stop")))

    def test_rate_limit_then_success_is_verified_and_checkpointed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.run_path(Path(temporary))
            adapter = FakeAdapter({"OP-001": ["rate-limit", "success"]})
            result = execute_ready_operations(
                path,
                adapter,
                timestamp=lambda: "2026-08-01T10:01:00Z",
            )
            saved = load_document(path)
        self.assertTrue(result["resumable"])
        self.assertEqual(saved["object_changes"][0]["state"], "verified")
        self.assertEqual(adapter.mutate_calls["OP-001"], 2)
        self.assertEqual(adapter.page_calls, [None, "page-2"])

    def test_auth_expiry_stops_dependents_and_preserves_partial_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.run_path(Path(temporary), count=3)
            adapter = FakeAdapter({"OP-001": ["success"], "OP-002": ["auth"]})
            execute_ready_operations(
                path,
                adapter,
                timestamp=lambda: "2026-08-01T10:01:00Z",
            )
            saved = load_document(path)
        states = {item["operation_id"]: item["state"] for item in saved["object_changes"]}
        self.assertEqual(
            states,
            {"OP-001": "verified", "OP-002": "failed", "OP-003": "planned"},
        )
        self.assertEqual(adapter.mutate_calls["OP-003"], 0)

    def test_ambiguous_write_uses_readback_and_never_blindly_retries(self) -> None:
        for behavior, expected_state in (
            ("ambiguous-saved", "verified"),
            ("ambiguous-absent", "uncertain"),
        ):
            with self.subTest(behavior=behavior), tempfile.TemporaryDirectory() as temporary:
                path = self.run_path(Path(temporary))
                adapter = FakeAdapter({"OP-001": [behavior, "success"]})
                execute_ready_operations(
                    path,
                    adapter,
                    timestamp=lambda: "2026-08-01T10:01:00Z",
                )
                saved = load_document(path)
                self.assertEqual(saved["object_changes"][0]["state"], expected_state)
                self.assertEqual(adapter.mutate_calls["OP-001"], 1)

    def test_existing_match_makes_rerun_a_noop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self.run_path(root)
            adapter = FakeAdapter()
            operation = load_document(path)["object_changes"][0]
            adapter.saved[operation["object_key"]] = {
                "intended": deepcopy(operation["intended"]),
                "object_id": "existing-id",
                "fingerprint": "existing-fp",
            }
            execute_ready_operations(
                path,
                adapter,
                timestamp=lambda: "2026-08-01T10:01:00Z",
            )
            saved = load_document(path)
        self.assertEqual(saved["object_changes"][0]["state"], "verified")
        self.assertEqual(adapter.mutate_calls["OP-001"], 0)

    def test_uncertain_checkpoint_blocks_automatic_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self.run_path(Path(temporary))
            adapter = FakeAdapter({"OP-001": ["ambiguous-absent"]})
            execute_ready_operations(
                path,
                adapter,
                timestamp=lambda: "2026-08-01T10:01:00Z",
            )
            with self.assertRaisesRegex(AdapterExecutionError, "resolve them by readback"):
                execute_ready_operations(path, adapter)


if __name__ == "__main__":
    unittest.main()
