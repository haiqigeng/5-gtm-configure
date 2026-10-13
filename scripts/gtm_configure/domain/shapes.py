"""Canonical collection shapes; pipeline wire cardinality is a separate model."""

FIELD_SHAPES = frozenset(
    {
        "scalar:string",
        "scalar:number",
        "scalar:integer",
        "scalar:boolean",
        "array",
        "object",
    }
)


def collection_shape(value):
    if value not in FIELD_SHAPES:
        raise ValueError(
            f"unsupported collection shape {value!r}; expected one of {sorted(FIELD_SHAPES)}"
        )
    return value


def plan_shape(value):
    return collection_shape(value if value in {"array", "object"} else f"scalar:{value}")
