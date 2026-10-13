"""Shared repository test imports; packaged tests remain self-contained."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / name) for name in ("scripts", "tools", "tests")]
