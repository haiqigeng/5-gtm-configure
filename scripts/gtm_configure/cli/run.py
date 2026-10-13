#!/usr/bin/env python3
"""CLI for the current configure-gtm run manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from gtm_configure.core.json_io import (
    StrictJsonError,
    load_json,
    validate_output_paths,
    write_text_atomic,
)
from gtm_configure.core.model import (
    OPERATION_STATES,
)
from gtm_configure.core.validation import (
    RunConflictError,
    RunValidationError,
)
from gtm_configure.render import render_markdown
from gtm_configure.runtime.adapter_protocol import atomic_write, run_file_lock
from gtm_configure.runtime.state import (
    checkpoint_operation,
    create_from_contract,
    inspect_document,
    load_document,
    reopen_failed_operation,
)


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
            if args.output:
                try:
                    validate_output_paths(inputs=[args.run], outputs=[args.output])
                except ValueError as exc:
                    raise RunValidationError(str(exc)) from exc
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
