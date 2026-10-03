"""Exercise the real host transport; all values here are synthetic."""

import os
import sys

sys.path.insert(0, os.environ["RUNTIME_SCRIPTS"])
from adapter_support import AdapterExecutionError
from mcp_adapter import unwrap
from mcp_transport import StdioTransport, completion, configure_terminal
from redaction import redact_for_persistence

configure_terminal()
transport = StdioTransport(timeout=300)
name = "Événement d'O’Brien ‘quoted’ “double” — 日本語"
large = "É日本語" * int(os.environ.get("RELAY_LARGE_REPEATS", "30000"))
result = transport("synthetic__gtm_tag", {"action": "get", "tagId": "1"})
assert unwrap(result)["name"] == name
result = transport(
    "synthetic__gtm_tag",
    {"action": "create", "createOrUpdateConfig": {"name": name, "notes": large}},
)
assert unwrap(result)["notes"] == large
for tool, action in (("gtm_workspace", "publish"), ("gtm_variable", "get")):
    try:
        transport("synthetic__" + tool, {"action": action})
    except AdapterExecutionError as exc:
        assert exc.code == "read_failed", exc.code
    else:
        raise AssertionError("Forbidden or failed request should fail closed")
result = transport("synthetic__gtm_tag", {"action": "get", "tagId": "sensitive"})
assert "SYNTHETIC_ONLY" not in str(redact_for_persistence(unwrap(result)))
completion({"status": "Synthetic relay done", "calls": transport.calls})
