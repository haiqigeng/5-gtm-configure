from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import tempfile
import threading
import unittest
from collections import Counter
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from fixtures.mcp_behavior_scenario import PROFILE, FakeGtm, request
from gtm_configure.adapters.mcp import McpTargetAdapter
from gtm_configure.cli.mcp_host import (
    HostSetupError,
    connection_diagnostic,
    load_connection,
    run_host,
)
from gtm_configure.core.privacy import contains_redacted, redact_for_persistence, sensitive_findings
from gtm_configure.core.public_identifiers import (
    public_identifier_paths,
    validate_public_identifiers,
)
from gtm_configure.intake.ga4 import normalized_approved_semantics, verify_delivery
from gtm_configure.intake.request import compile_request  # noqa: E402
from gtm_configure.render import render_markdown
from gtm_configure.runtime.adapter_protocol import atomic_write
from gtm_configure.runtime.engine import (
    AdapterExecutionError,
    TargetAdapterRegistry,
    execute_ready_operations,
    verify_idempotent_rerun,
)
from gtm_configure.runtime.state import (
    create_from_contract,  # noqa: E402
    load_document,
)

from support.privacy_shapes import public_contract

ROOT = Path(__file__).resolve().parents[2]


def run_document():
    return create_from_contract(
        compile_request(request()),
        run_id="audit-followup",
        source_locator="Synthetic approved request",
    )


class Audit102FollowupFixture(unittest.TestCase):
    pass


__all__ = [
    "AdapterExecutionError",
    "Audit102FollowupFixture",
    "BaseHTTPRequestHandler",
    "Counter",
    "FakeGtm",
    "HostSetupError",
    "McpTargetAdapter",
    "PROFILE",
    "Path",
    "ROOT",
    "TargetAdapterRegistry",
    "ThreadingHTTPServer",
    "asyncio",
    "atomic_write",
    "connection_diagnostic",
    "contains_redacted",
    "deepcopy",
    "execute_ready_operations",
    "hashlib",
    "json",
    "load_connection",
    "load_document",
    "normalized_approved_semantics",
    "patch",
    "public_contract",
    "public_identifier_paths",
    "quote",
    "redact_for_persistence",
    "render_markdown",
    "request",
    "run_document",
    "run_host",
    "sensitive_findings",
    "sys",
    "tempfile",
    "threading",
    "validate_public_identifiers",
    "verify_delivery",
    "verify_idempotent_rerun",
]
