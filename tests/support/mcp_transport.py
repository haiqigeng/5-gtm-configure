from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def profile(*families):
    return {
        "tool_prefix": "synthetic__",
        "workspace_path": [],
        "container_path": [],
        "status_path": [],
        "families": {
            family: {
                "actions": ["get", "list", "create", "update", "remove"],
                "first_page": 1,
                "page_size": 2,
                "list_path": [family],
                "object_path": [],
            }
            for family in families
        },
    }


class McpTransportTestsFixture(unittest.TestCase):
    pass
