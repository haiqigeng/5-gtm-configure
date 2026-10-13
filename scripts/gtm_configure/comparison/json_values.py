"""Type-strict recursive comparison of normalized JSON values."""

from typing import Any


def differences(expected: Any, actual: Any, path: str = "$") -> list[dict[str, Any]]:
    if type(expected) is not type(actual):
        return [
            {
                "path": path,
                "kind": "type_mismatch",
                "expected": expected,
                "actual": actual,
            }
        ]
    if isinstance(expected, dict):
        output: list[dict[str, Any]] = []
        expected_keys = set(expected)
        actual_keys = set(actual)
        for key in sorted(expected_keys - actual_keys):
            output.append({"path": f"{path}.{key}", "kind": "missing", "expected": expected[key]})
        for key in sorted(actual_keys - expected_keys):
            output.append({"path": f"{path}.{key}", "kind": "extra", "actual": actual[key]})
        for key in sorted(expected_keys & actual_keys):
            output.extend(differences(expected[key], actual[key], f"{path}.{key}"))
        return output
    if isinstance(expected, list):
        if len(expected) == len(actual) and all(
            not differences(left, right) for left, right in zip(expected, actual)
        ):
            return []
        return [
            {
                "path": path,
                "kind": "array_mismatch",
                "expected": expected,
                "actual": actual,
            }
        ]
    if expected != actual:
        return [
            {
                "path": path,
                "kind": "value_mismatch",
                "expected": expected,
                "actual": actual,
            }
        ]
    return []
