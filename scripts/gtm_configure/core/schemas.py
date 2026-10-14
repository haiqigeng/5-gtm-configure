"""Cached local JSON Schema validators; no network resolution or second structure model."""

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


@lru_cache(maxsize=3)
def validator(kind):
    root = Path(__file__).resolve().parents[3] / "schemas"
    documents = [json.loads(p.read_text(encoding="utf-8")) for p in root.glob("*.schema.json")]
    registry = Registry().with_resources(
        (doc["$id"], Resource.from_contents(doc)) for doc in documents
    )
    schema = next(
        doc
        for doc in documents
        if doc["$id"].endswith(
            "common.schema.json" if kind == "common" else f"configuration-{kind}.schema.json"
        )
    )
    return Draft202012Validator(schema, registry=registry)


def validate_structure(value, kind, fail):
    _validate(value, validator(kind), fail)


@lru_cache(maxsize=None)
def definition_validator(name):
    common = validator("common")
    return common.evolve(schema={"$ref": common.schema["$id"] + "#/$defs/" + name})


def validate_definition(value, name, fail):
    """Validate a public declaration API against the same phase-boundary schema."""
    _validate(value, definition_validator(name), fail)


def _validate(value, schema_validator, fail):
    error = next(schema_validator.iter_errors(value), None)
    if error is not None:
        path = "$" + "".join(
            f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path
        )
        fail(f"{path}: {error.message}")


@lru_cache(maxsize=1)
def field_collections():
    """The shared schema owns collection namespaces and producer destination routes."""
    properties = validator("common").schema["$defs"]["requirementSemantics"]["properties"]
    return {
        name: row["x-field-model"] for name, row in properties.items() if "x-field-model" in row
    }
