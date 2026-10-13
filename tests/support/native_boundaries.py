from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from fixtures.mcp_behavior_scenario import PROFILE, FakeGtm, request
from gtm_configure.adapters.mcp import McpTargetAdapter
from gtm_configure.comparison.native import GraphError
from gtm_configure.core.json_io import validate_output_paths
from gtm_configure.intake.request import compile_request
from gtm_configure.runtime.adapter_protocol import AdapterExecutionError, atomic_write
from gtm_configure.runtime.engine import (
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from gtm_configure.runtime.state import checkpoint_operation, create_from_contract, load_document
from gtm_configure.runtime.verification import (
    build_pre_write_comparison,
    build_verification_comparison,
)

from support.consent_and_fields import additional_request

ROOT = Path(__file__).resolve().parents[2]


class NativeBoundaryTestsFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "run.json"

    def start(self, req, call, profile=PROFILE):
        contract = compile_request(req)
        atomic_write(
            self.path,
            create_from_contract(
                contract, run_id="audit", source_locator="Synthetic approved request"
            ),
        )
        return self.registry(req, call, profile)

    def registry(self, req, call, profile=PROFILE):
        target = req["targets"][0]
        adapter = McpTargetAdapter(target, profile, call)
        registry = TargetAdapterRegistry()
        registry.register(target, adapter, adapter.capabilities())
        return registry, adapter

    def assert_configured(self, registry):
        verify_idempotent_rerun(self.path, registry)
        self.assertEqual(load_document(self.path)["run"]["status"], "Configured")


class PrewriteSemanticTestsFixture(unittest.TestCase):
    pass


class OutputAliasTestsFixture(unittest.TestCase):
    pass


__all__ = [
    "AdapterExecutionError",
    "FakeGtm",
    "GraphError",
    "NativeBoundaryTestsFixture",
    "OutputAliasTestsFixture",
    "PROFILE",
    "Path",
    "PrewriteSemanticTestsFixture",
    "ROOT",
    "additional_request",
    "atomic_write",
    "build_pre_write_comparison",
    "build_verification_comparison",
    "checkpoint_operation",
    "deepcopy",
    "execute_ready_operations",
    "load_document",
    "os",
    "request",
    "subprocess",
    "sys",
    "tempfile",
    "validate_output_paths",
]
