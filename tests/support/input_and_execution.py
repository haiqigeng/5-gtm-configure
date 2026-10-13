from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from gtm_configure.adapters.mcp import unwrap
from gtm_configure.adapters.transport import StdioTransport
from gtm_configure.contract import validate_document as validate_contract
from gtm_configure.core.privacy import is_redacted, redact_for_persistence, sensitive_paths
from gtm_configure.intake.ga4 import normalized_approved_semantics, verify_delivery
from gtm_configure.intake.request import compile_request
from gtm_configure.render import render_markdown
from gtm_configure.runtime.adapter_protocol import atomic_write
from gtm_configure.runtime.engine import (
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from gtm_configure.runtime.state import create_from_contract, load_document
from gtm_configure.runtime.validation import validate_document

from support.adapters import FakeAdapter, capabilities
from support.contracts import approve_mutations, valid_web_contract

ROOT = Path(__file__).resolve().parents[2]

CANARY = "CANARYsecretVALUE_7f3a9c1e5b2d8f4a6c0e"


def row(name, value=CANARY, name_key="parameter", value_key="parameterValue"):
    return {
        "type": "map",
        "map": [
            {"type": "template", "key": name_key, "value": name},
            {"type": "template", "key": value_key, "value": value},
        ],
    }


def compact(contract):
    value = deepcopy(contract)
    implementation = value.pop("implementation")
    value.update(implementation)
    value.pop("scope")
    for item in value["objects"]:
        for key in ("object_key", "target_id", "requirement_ids", "approval"):
            item.pop(key, None)
    return value


class AuditRegressionsFixture(unittest.TestCase):
    pass


__all__ = [
    "AuditRegressionsFixture",
    "CANARY",
    "FakeAdapter",
    "Path",
    "ROOT",
    "StdioTransport",
    "TargetAdapterRegistry",
    "approve_mutations",
    "atomic_write",
    "capabilities",
    "compact",
    "compile_request",
    "create_from_contract",
    "deepcopy",
    "execute_ready_operations",
    "io",
    "is_redacted",
    "json",
    "load_document",
    "normalized_approved_semantics",
    "patch",
    "redact_for_persistence",
    "render_markdown",
    "row",
    "sensitive_paths",
    "shutil",
    "tempfile",
    "unwrap",
    "valid_web_contract",
    "validate_contract",
    "validate_document",
    "verify_delivery",
    "verify_idempotent_rerun",
]
