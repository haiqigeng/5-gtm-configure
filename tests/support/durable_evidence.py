from __future__ import annotations

import unittest
from copy import deepcopy
from pathlib import Path

from gtm_configure.contract import ContractValidationError
from gtm_configure.contract import validate_document as validate_contract
from gtm_configure.core.privacy import redact_for_persistence, redacted_marker, sensitive_paths
from gtm_configure.core.validation import RunValidationError
from gtm_configure.render import render_markdown
from gtm_configure.runtime.state import (
    checkpoint_operation,
    create_from_contract,
    finalize_adapter_verified_document,
    reopen_failed_operation,
)
from gtm_configure.runtime.validation import validate_document as validate_run
from gtm_configure.runtime.verification import (
    build_pre_write_comparison,
    build_verification_comparison,
    canonical_sha256,
    expected_graph,
    materialization_fingerprints,
)

from support.contracts import (  # noqa: E402
    add_nonpurchase_dual_dedup,
    approve_mutations,
    valid_pipeline_contract,
    valid_server_contract,
    valid_web_contract,
    with_complete_baselines,
)

ROOT = Path(__file__).resolve().parents[2]


def materialize(contract: dict) -> dict:
    approve_mutations(contract)
    return with_complete_baselines(
        create_from_contract(
            contract,
            run_id="RUN-HARDENING",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
    )


class CurrentRegressionHardeningTestFixture(unittest.TestCase):
    pass


__all__ = [
    "ContractValidationError",
    "CurrentRegressionHardeningTestFixture",
    "RunValidationError",
    "add_nonpurchase_dual_dedup",
    "approve_mutations",
    "build_pre_write_comparison",
    "build_verification_comparison",
    "canonical_sha256",
    "checkpoint_operation",
    "deepcopy",
    "expected_graph",
    "finalize_adapter_verified_document",
    "materialization_fingerprints",
    "materialize",
    "redact_for_persistence",
    "redacted_marker",
    "render_markdown",
    "reopen_failed_operation",
    "sensitive_paths",
    "valid_pipeline_contract",
    "valid_server_contract",
    "valid_web_contract",
    "validate_contract",
    "validate_run",
]
