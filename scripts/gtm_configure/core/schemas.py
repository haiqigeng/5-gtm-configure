"""Cached local JSON Schema validators; no network resolution or second structure model."""

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


@lru_cache(maxsize=2)
def validator(kind):
    root = Path(__file__).resolve().parents[3] / "schemas"
    documents = [json.loads(p.read_text(encoding="utf-8")) for p in root.glob("*.schema.json")]
    registry = Registry().with_resources(
        (doc["$id"], Resource.from_contents(doc)) for doc in documents
    )
    schema = next(
        doc for doc in documents if doc["$id"].endswith(f"configuration-{kind}.schema.json")
    )
    return Draft202012Validator(schema, registry=registry)


def validate_structure(value, kind, fail):
    error = next(validator(kind).iter_errors(value), None)
    if error is not None:
        path = "$" + "".join(
            f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path
        )
        fail(f"{path}: {error.message}")
