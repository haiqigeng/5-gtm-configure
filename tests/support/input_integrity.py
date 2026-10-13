from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from gtm_configure.core.json_io import StrictJsonError, load_json, loads_strict
from gtm_configure.intake.ga4 import HandoffError, normalized_approved_semantics, verify_delivery

ROOT = Path(__file__).resolve().parents[2]


def valid_plan() -> dict:
    return {
        "schema_version": "6.0.0",
        "future_metadata": {"producer": "accepted without reinterpretation"},
        "events": [
            {
                "event_name": "generate_lead",
                "classification": "official",
                "journey_ids": ["lead_form"],
                "measurement_opportunity_ids": ["lead_submission"],
                "trigger": "After the confirmed form success",
                "data_layer": {"clear": [], "push": {"event": "generate_lead"}},
                "parameters": [
                    {
                        "name": "method",
                        "scope": "event",
                        "type": "string",
                        "requirement": "required",
                        "data_layer_path": "event_data.method",
                        "destination": "ga4_event_parameter",
                        "future_metadata": "retained upstream",
                    }
                ],
                "future_metadata": {"reviewed": True},
            }
        ],
    }


class RuntimeHardeningTestFixture(unittest.TestCase):
    pass


__all__ = [
    "HandoffError",
    "Path",
    "ROOT",
    "RuntimeHardeningTestFixture",
    "StrictJsonError",
    "deepcopy",
    "hashlib",
    "json",
    "load_json",
    "loads_strict",
    "normalized_approved_semantics",
    "subprocess",
    "sys",
    "tempfile",
    "valid_plan",
    "verify_delivery",
]
