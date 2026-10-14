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
`common.schema.json` owns requirement fields, execution, page-view, identity, payload and external
dependency declarations, assertions, consent, field flows and approval hashes. Its field registry
drives destination import, mappings and preparation. Approved projections share schema and scope
validation with contract intake. `runtime/readiness.py` resolves native field owners, ready demand
on shared dependencies and transitive blockers for inspection and manual/executor checkpoints.
`domain/native.py` owns supported native namespaces; explicit field bindings are validated at every
status before mapped-value proof. Shared objects remain available to ready consumers unless their
own fields or dependencies block them. Contract requirements
carry full approved semantics; run requirements are closed execution summaries using the same
semantic field definitions. Run status and operation links belong to the run schema.
`domain/context.py` converts each phase once into `ConfigurationGraph`; domain validators consume
that graph. Target localization preserves native pre-change snapshots and converts intended semantic
references. Feature predicates live with execution, page views, first-party data or inventory.
`core/validation.py` owns canonical JSON hashing (`sha256:<hex>`) and typed accessors; raw delivery
artifact hashes retain their producer-defined byte-hash format.
Reference folders follow the task's decisions, with separate host and vendor surfaces loaded on demand.

Repository maintainers run `tools/check_release.py` for architecture, schema versions, routed links,
file labels, CLI usage and package checks. `tools/check_architecture.py --output ownership.json`
derives the full file/import map, schema constraints, function failure sites and document links.
The gate detects literal copies of complete closed schema key sets in local or module scope.
Tests are grouped by behavior owner; reusable native graphs and
adapters live in `tests/support`. Repository-only checks and fixtures stay outside the installed skill.

Current release is 13.0.1, contract 10.0, run 8.0. No old entry points, schema migrations or
compatibility fallbacks are shipped. Re-author a pending change with the current model; retain
historical executed artifacts as evidence and resolve uncertain writes before starting another run.
