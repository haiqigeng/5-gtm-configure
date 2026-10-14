"""Actual worker transport cancellation while its run lock and a write are active."""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["RUNTIME_SCRIPTS"])
from gtm_configure.adapters.transport import (
    HostCancelledError,
    StdioTransport,
    completion,
    configure_terminal,
)
from gtm_configure.core.json_io import write_json_atomic
from gtm_configure.runtime.adapter_protocol import run_file_lock

run_path = Path(sys.argv[sys.argv.index("--run") + 1])
configure_terminal()
transport = StdioTransport(timeout=30)
with run_file_lock(run_path):
    try:
        transport(
            "synthetic__gtm_tag",
            {"action": "create", "createOrUpdateConfig": {"name": "Équipe 日本語"}},
        )
        raise AssertionError("The interrupted host must not deliver a success response")
    except HostCancelledError:
        result = {"status": "Interrupted", "writes_attempted": transport.writes_attempted}
        write_json_atomic(run_path.with_suffix(".execution.json"), result)
completion(result)
