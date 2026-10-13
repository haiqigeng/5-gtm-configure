"""Local schema registry for independent structural tests."""

import json
from functools import lru_cache
from pathlib import Path

from referencing import Registry, Resource


@lru_cache(maxsize=1)
def schema_registry():
    root = Path(__file__).resolve().parents[2] / "schemas"
    documents = [json.loads(p.read_text(encoding="utf-8")) for p in root.glob("*.json")]
    return Registry().with_resources((d["$id"], Resource.from_contents(d)) for d in documents)
