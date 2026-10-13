from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from support.contracts import approve_mutations, valid_web_contract

ROOT = Path(__file__).resolve().parents[2]

PUBLIC = "synthetic-public-browser-project"

SOURCE = "https://amplitude.com/docs/apis/keys-and-tokens"


def public_contract():
    contract = valid_web_contract()
    contract["evidence"].append(
        {
            "grade": "official-current",
            "locator": SOURCE,
            "title": "Synthetic evidence fixture",
            "decision": "Fixture represents inspected public browser key semantics, not a live vendor check",
            "accessed_on": "2026-09-28",
            "supports": ["REQ-PAGE"],
        }
    )
    contract["implementation"]["objects"].append(
        {
            "object_key": "web-main::variable::Amplitude API Key",
            "target_id": "web-main",
            "resource_family": "variable",
            "name": "Amplitude API Key",
            "action": "create",
            "requirement_ids": ["REQ-PAGE"],
            "depends_on": [],
            "justification": "Synthetic approved public key fixture",
            "evidence": ["approved-input", "official-current"],
            "risk": "routine",
            "intended": {
                "type": "c",
                "parameter": [{"key": "value", "type": "template", "value": PUBLIC}],
            },
            "public_identifiers": [
                {
                    "path": ["parameter", "value", "value"],
                    "value_sha256": hashlib.sha256(PUBLIC.encode()).hexdigest(),
                    "source_url": SOURCE,
                    "reason": "Inspected browser collection identifier, not an authentication secret",
                }
            ],
        }
    )
    return approve_mutations(contract)


class RedactionShapeTestsFixture(unittest.TestCase):
    pass
