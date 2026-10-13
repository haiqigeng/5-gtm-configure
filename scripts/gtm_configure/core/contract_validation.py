"""Contract errors and small typed accessors, independent of domain rules."""

from typing import Any

from gtm_configure.core.model import EVIDENCE_GRADES


class ContractValidationError(ValueError):
    """Raised when the current contract cannot safely authorize deterministic materialization."""

    def __init__(self, message: str, *, error_code: str = "invalid_contract") -> None:
        super().__init__(message)
        self.error_code = error_code


def _fail(message: str) -> None:
    raise ContractValidationError(message)


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractValidationError(f"{path} must be an object")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractValidationError(f"{path} must be an array")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{path} must be a non-empty string")
    return value.strip()


def _unique_texts(value: Any, path: str, *, allow_empty: bool = True) -> list[str]:
    items = [_text(item, f"{path}[]") for item in _array(value, path)]
    if not allow_empty and not items:
        raise ContractValidationError(f"{path} must not be empty")
    if len(set(items)) != len(items):
        raise ContractValidationError(f"{path} contains duplicate values")
    return items


def _authority(value: Any, path: str, *, approved: bool = False) -> dict[str, Any]:
    authority = _object(value, path)
    grade = _text(authority.get("grade"), f"{path}.grade")
    if grade not in EVIDENCE_GRADES:
        raise ContractValidationError(f"{path}.grade has unsupported value {grade!r}")
    if approved and grade != "approved-input":
        raise ContractValidationError(f"{path}.grade must be 'approved-input'")
    _text(authority.get("locator"), f"{path}.locator")
    return authority
