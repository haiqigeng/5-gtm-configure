"""Contract errors and small typed accessors, independent of domain rules."""

from functools import partial
from typing import Any

from gtm_configure.core import validation
from gtm_configure.core.model import EVIDENCE_GRADES


class ContractValidationError(ValueError):
    """Raised when the current contract cannot safely authorize deterministic materialization."""

    def __init__(self, message: str, *, error_code: str = "invalid_contract") -> None:
        super().__init__(message)
        self.error_code = error_code


def fail(message: str) -> None:
    raise ContractValidationError(message)


object = partial(validation.object, error_type=ContractValidationError)
array = partial(validation.array, error_type=ContractValidationError)
text = partial(validation.text, error_type=ContractValidationError)
unique_texts = partial(validation.unique_texts, error_type=ContractValidationError)


def authority(value: Any, path: str, *, approved: bool = False) -> dict[str, Any]:
    authority = object(value, path)
    grade = text(authority.get("grade"), f"{path}.grade")
    if grade not in EVIDENCE_GRADES:
        raise ContractValidationError(f"{path}.grade has unsupported value {grade!r}")
    if approved and grade != "approved-input":
        raise ContractValidationError(f"{path}.grade must be 'approved-input'")
    text(authority.get("locator"), f"{path}.locator")
    return authority
