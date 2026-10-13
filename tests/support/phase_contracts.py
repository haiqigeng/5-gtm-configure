from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from gtm_configure.contract import ContractValidationError
from gtm_configure.contract import validate_document as validate_contract
from gtm_configure.core.privacy import (
    REDACTED_STATE,
    redact_for_persistence,
    redacted_marker,
    safe_equal,
    sensitive_paths,
)
from gtm_configure.core.validation import RunValidationError
from gtm_configure.runtime.state import (
    checkpoint_operation,
    create_from_contract,
    record_target_baseline,
)
from gtm_configure.runtime.verification import build_verification_comparison, expected_graph
from jsonschema import Draft202012Validator

from support.contracts import (
    add_nonpurchase_dual_dedup,
    complete_capture_evidence,
    valid_pipeline_contract,
    valid_server_contract,
    valid_web_contract,
)
from support.schemas import schema_registry

ROOT = Path(__file__).resolve().parents[2]


class CurrentContractAndRunTestFixture(unittest.TestCase):
    pass


__all__ = [
    "ContractValidationError",
    "CurrentContractAndRunTestFixture",
    "Draft202012Validator",
    "Path",
    "REDACTED_STATE",
    "ROOT",
    "RunValidationError",
    "add_nonpurchase_dual_dedup",
    "build_verification_comparison",
    "checkpoint_operation",
    "complete_capture_evidence",
    "create_from_contract",
    "deepcopy",
    "expected_graph",
    "json",
    "record_target_baseline",
    "redact_for_persistence",
    "redacted_marker",
    "safe_equal",
    "schema_registry",
    "sensitive_paths",
    "subprocess",
    "sys",
    "tempfile",
    "valid_pipeline_contract",
    "valid_server_contract",
    "valid_web_contract",
    "validate_contract",
]
