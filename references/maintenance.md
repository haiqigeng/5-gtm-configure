# Maintaining this skill

Run `python -B -m pytest "<skill-dir>/tests" -q -p no:cacheprovider` for the offline behavioral suite.
The selected environment needs pytest as a test-only dependency; ordinary execution uses only
`scripts/requirements.txt`, or `requirements-mcp.txt` for the SDK host adapter.
Run the skill-creator `quick_validate.py` against this directory for frontmatter/scaffolding checks.
Neither check certifies live GTM, template behavior, runtime delivery, or every host integration.

`scripts/configure_gtm.py` is the only CLI router. `gtm_configure/intake` translates approved input;
`contract.py` coordinates structural and semantic preflight; `domain` owns shared feature rules;
`runtime` owns durable state and adapter execution; `adapters` owns transport; `comparison` owns
type-strict equality with native normalization; `core` owns JSON, privacy, errors and enums.
The JSON schemas own structural validation; cached validators resolve only packaged schemas.
Reference folders follow the task's decisions, with separate host and vendor surfaces loaded on demand.

Current release is 11.0.0, contract 8.0, run 6.0. No old entry points, schema migrations or
compatibility fallbacks are shipped. Re-author a pending change with the current model; retain
historical executed artifacts as evidence and resolve uncertain writes before starting another run.
