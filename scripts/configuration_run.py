#!/usr/bin/env python3
"""CLI and public API for the current configure-gtm run manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import run_state
import run_validation_web as web_support
from adapter_support import atomic_write, run_file_lock
from run_model import OPERATION_STATES, RUN_PHASES, RUN_STATUSES, SCHEMA_VERSION
from run_model_web import FIRST_PARTY_FEATURES
from run_render import render_markdown as render_current_markdown
from run_validation_core import validate_document as validate_current_document
from strict_json import StrictJsonError, load_json, write_text_atomic
from verification import build_pre_write_comparison as build_current_pre_write_comparison
from verification import build_verification_comparison as build_current_verification_comparison
from verification import canonical_sha256
from verification import validate_verification_comparison as validate_current_comparison

__all__ = [
    "FIRST_PARTY_FEATURES",
    "OPERATION_STATES",
    "RUN_PHASES",
    "RUN_STATUSES",
    "SCHEMA_VERSION",
    "RunConflictError",
    "RunValidationError",
    "atomic_write",
    "build_pre_write_comparison",
    "build_verification_comparison",
    "canonical_sha256",
    "checkpoint_operation",
    "create_from_contract",
    "inspect_document",
    "load_document",
    "render_markdown",
    "reopen_failed_operation",
    "run_file_lock",
    "validate_document",
    "validate_verification_comparison",
]

RunValidationError = web_support.RunValidationError
RunConflictError = web_support.RunConflictError


def validate_document(value: Any) -> dict[str, Any]:
    return validate_current_document(value)


def load_document(path: Path) -> dict[str, Any]:
    return run_state.load_document(path)


def create_from_contract(
    contract: dict[str, Any],
    *,
    run_id: str,
    source_locator: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    return run_state.create_from_contract(
        contract,
        run_id=run_id,
        source_locator=source_locator,
        timestamp=timestamp,
    )


def inspect_document(document: dict[str, Any]) -> dict[str, Any]:
    return run_state.inspect_document(document)


def checkpoint_operation(document: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return run_state.checkpoint_operation(document, **kwargs)


def reopen_failed_operation(document: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return run_state.reopen_failed_operation(document, **kwargs)


def render_markdown(document: dict[str, Any], *, embed_machine: bool = False) -> str:
    return render_current_markdown(validate_current_document(document), embed_machine=embed_machine)


def build_verification_comparison(operation: dict[str, Any], saved: Any) -> Any:
    return build_current_verification_comparison(operation, saved)


def validate_verification_comparison(operation: dict[str, Any], comparison: Any, saved: Any) -> Any:
    return validate_current_comparison(operation, comparison, saved)


def build_pre_write_comparison(operation: dict[str, Any], saved: Any) -> Any:
    return build_current_pre_write_comparison(operation, saved)


def _emit_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, allow_nan=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--run", type=Path, required=True)
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--contract", type=Path, required=True)
    init_parser.add_argument("--run-id", required=True)
    init_parser.add_argument("--source-locator", required=True)
    init_parser.add_argument("--timestamp")
    init_parser.add_argument("--output", type=Path, required=True)
    init_parser.add_argument("--replace-planned", action="store_true")
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--run", type=Path, required=True)
    checkpoint_parser = subparsers.add_parser("checkpoint")
    checkpoint_parser.add_argument("--run", type=Path, required=True)
    checkpoint_parser.add_argument("--operation", required=True)
    checkpoint_parser.add_argument(
        "--state", choices=sorted(OPERATION_STATES - {"planned"}), required=True
    )
    checkpoint_parser.add_argument("--note", required=True)
    checkpoint_parser.add_argument("--timestamp")
    checkpoint_parser.add_argument("--result", type=Path)
    checkpoint_parser.add_argument("--comparison", type=Path)
    checkpoint_parser.add_argument("--saved-readback", type=Path)
    checkpoint_parser.add_argument("--pre-write-comparison", type=Path)
    checkpoint_parser.add_argument("--pre-write-readback", type=Path)
    checkpoint_parser.add_argument("--error")
    reopen_parser = subparsers.add_parser("reopen")
    reopen_parser.add_argument("--run", type=Path, required=True)
    reopen_parser.add_argument("--operation", required=True)
    reopen_parser.add_argument("--note", required=True)
    reopen_parser.add_argument("--timestamp")
    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("--run", type=Path, required=True)
    render_parser.add_argument("--output", type=Path)
    render_parser.add_argument("--embed-machine", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "validate":
            document = load_document(args.run)
            _emit_json({"pass": True, "schema_version": document["schema_version"]})
        elif args.command == "init":
            contract = load_json(args.contract)
            document = create_from_contract(
                contract,
                run_id=args.run_id,
                source_locator=args.source_locator,
                timestamp=args.timestamp,
            )
            with run_file_lock(args.output):
                if args.output.exists() and not args.replace_planned:
                    raise RunValidationError("output already exists; select a new path")
                if args.output.exists() and args.replace_planned:
                    existing = load_document(args.output)
                    if any(
                        item["state"] != "planned" or item["journal"]
                        for item in existing["object_changes"]
                    ):
                        raise RunValidationError("--replace-planned refuses saved run history")
                atomic_write(args.output, document)
            _emit_json({"pass": True, "output": str(args.output.resolve())})
        elif args.command == "inspect":
            _emit_json(inspect_document(load_document(args.run)))
        elif args.command == "checkpoint":
            kwargs: dict[str, Any] = {
                "operation_id": args.operation,
                "state": args.state,
                "note": args.note,
                "timestamp": args.timestamp,
                "result": load_json(args.result) if args.result else None,
                "comparison": load_json(args.comparison) if args.comparison else None,
                "pre_write_comparison": (
                    load_json(args.pre_write_comparison) if args.pre_write_comparison else None
                ),
                "error": args.error,
            }
            if args.saved_readback:
                kwargs["saved"] = load_json(args.saved_readback)
            if args.pre_write_readback:
                kwargs["pre_write_saved"] = load_json(args.pre_write_readback)
            with run_file_lock(args.run):
                document = checkpoint_operation(load_document(args.run), **kwargs)
                atomic_write(args.run, document)
            _emit_json({"pass": True, "operation": args.operation, "state": args.state})
        elif args.command == "reopen":
            with run_file_lock(args.run):
                document = reopen_failed_operation(
                    load_document(args.run),
                    operation_id=args.operation,
                    note=args.note,
                    timestamp=args.timestamp,
                )
                atomic_write(args.run, document)
            _emit_json({"pass": True, "operation": args.operation, "state": "planned"})
        else:
            rendered = render_markdown(load_document(args.run), embed_machine=args.embed_machine)
            if args.output:
                write_text_atomic(args.output, rendered)
                _emit_json({"pass": True, "output": str(args.output.resolve())})
            else:
                sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
                print(rendered, end="")
    except (RunConflictError, RunValidationError, StrictJsonError) as exc:
        error_code = (
            "run_conflict"
            if isinstance(exc, RunConflictError)
            else getattr(exc, "error_code", "invalid_run")
        )
        _emit_json(
            {
                "pass": False,
                "error_code": error_code,
                "error": str(exc),
            }
        )
        return 2
    except (OSError, UnicodeError) as exc:
        _emit_json({"pass": False, "error_code": "io_error", "error": str(exc)})
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
