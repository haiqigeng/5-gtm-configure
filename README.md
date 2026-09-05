# Configure GTM

An agent-neutral operational skill for expert web analysts configuring Google Tag Manager web
containers, server containers, or their connected event pipeline. It converts approved analytics
requirements and explicit media briefs into clean, consent-controlled, saved and verified GTM
object graphs. It never publishes and never substitutes configuration for runtime recette.

## Current Release

**v10.0.0** makes the routed web, server, and pipeline configurator current-only and closes the
utility and correctness gaps found in independent evaluation. Authority, baselines, adapter
capabilities, mutations, readback, recovery, and status remain isolated per target.

Existing coverage includes GTM server Clients, Event Data variables, server triggers/tags/templates,
Transformations, GA4 and media destinations, transport ownership, consent propagation, field-shape
proof, first-party-data and secret handling, destination-specific browser/server deduplication,
receiver-first cutover ordering, dependency-only failure containment, and evidence-backed
human/machine configuration results without coupling the skill to runtime recette tooling.

Known execution boundary: triggerless setup/cleanup-only tags cannot be represented by the current
topology. Hold those requirements without inventing ordinary triggers; they are excluded from
this release's field-test acceptance.

Mutation contracts use only `configuration-contract@7.0`; execution uses only
`configuration-run@4.0`. Obsolete contract/run schemas and upgrade paths are intentionally absent.

## North Star

Operationally implement approved analytics requirements and explicit media briefs across authorized
GTM web and associated server workspaces as clean, well-organized, technically correct,
best-practice, consent-controlled saved object graphs connected by an explicit verified pipeline.

The unit of success is the saved and readback-verified graph for every authorized target. For a
pipeline it also includes static proof from sender through the one intended claiming Client and
generated Event Data to every required server consumer. A plan, prose specification, one-sided
pipeline, unsafe cutover, or runtime expectation is not configuration.

## Operating Routes

- `web` covers the complete supported client-side configuration surface and defaults.
- `server` configures explicitly authorized server-container workspaces using server semantics.
- `pipeline` configures the connected sender/receiver graph; several web senders may feed one
  Client and one claimed event may fan out to several destinations.

A named web target never grants authority over a discovered server endpoint, and server authority
never grants web access. Routine create/update/reuse is implied only inside each named target's
dedicated workspace. High-impact changes retain their explicit authority gates.

## Utility Surface

The web route configures tags, normal and blocking triggers, user-defined and built-in variables,
templates, folders, Google tag configuration/destinations, workspaces, and explicitly authorized
Zones, environments, and settings. It supports GA4, documented non-GA4 analytics, Google Ads,
Floodlight, Microsoft Advertising, Meta, TikTok, Snap, LinkedIn, Pinterest, X, Reddit, Criteo,
affiliate/partner tags, and unlisted documented products.

The server route configures supported Clients, tags, Event Data/template variables, server
triggers, folders, templates, narrow Transformations, and settings. Every browser media playbook has
a server counterpart. Guidance parity does not invent a supported GTM template: a route blocks or
defers when the exact product, official schema, template, credentials owner, consent, or dedup path
cannot be proved.

The pipeline route additionally resolves:

- one transport owner and safe environment endpoint routing;
- page-view ownership and effective `send_page_view`;
- exactly one intended Client per request class and receiver fan-out;
- source, web variable, wire, Client, Event Data, server owner, template, and destination field
  shape;
- per-destination web/transport/server consent topology and event coverage;
- browser-only, server-only/replacement, dual-shared-ID, or template-native delivery;
- receiver-first mutation and live endpoint cutover last; and
- external rollout order without publishing it.

## Important Defaults

- Preserve approved analytics events, fields, literals, filters, sources, and success timing.
  Official documentation validates technical feasibility; it does not silently redesign valid
  analytics semantics.
- Media intent comes from a human brief. Current official product documentation and the inspected
  installed template control each browser/server destination schema.
- Select best-practice architecture before reuse. Existing prevalence is integration evidence,
  never architecture authority.
- Use native or supported templates before browser Custom HTML or a custom server route. Inspect
  publisher, version, fields, defaults, permissions, hosts, secret handling, and automatic behavior.
- Keep web strict/basic CMP control by default: baseline tags use a verified CMP lifecycle trigger
  plus vendor block; business tags use their business trigger plus vendor block. Do not stack an
  equivalent Additional Consent Check.
- Configure Google Consent Mode web-side; consent-aware server Google tags process the incoming
  signal. Non-Google server gates use only approved documented state with complete event coverage.
- `items` is an array and `user_data` is an object. Prove every non-scalar shape through the
  sender, claiming Client, Event Data, and receiving template; never encode a universal two-array
  rule or silently flatten/drop data.
- Scope first-party data by event and consumer. `user_id`, `user_data`, GA4 user properties,
  Configuration Settings, and Event Settings have distinct owners. Redact raw PII and secrets
  before persistence.
- Create no dedup contract for single-channel delivery. For dual delivery, use one current
  vendor-documented occurrence identity across browser and server. A dual-delivery purchase needs
  a stable product-supported transaction/order/occurrence identity. If no stable occurrence identity
  exists, choose another delivery strategy or leave that dual route blocked.
- Do not synthesize browser/server occurrence identity from GTM internals. Browser-only runs still
  do not generate an event ID.
- Never create payload-eligibility helpers or validity triggers merely because a runtime value may
  be absent.

## Execution And Recovery

Contract 7.0 deterministically materializes target-scoped operation keys of the form:

`<target-id>::<resource-family>::<semantic-name>`

Contract-owned run sections carry fingerprints. Adapters may update baselines, journals,
comparisons, readbacks, results, and recovery state; they cannot silently rewrite intention. Each
write gets fresh pre-change proof where applicable and authoritative post-write readback. Baselines
are captured directly through the authenticated adapter immediately before the first write; the
runtime retains the redacted canonical object graph and creates exhaustion receipts itself. There
is no caller-supplied baseline command.

The immutable projection includes target identity, official sources, external dependencies,
client execution topologies, page-view ownership, first-party routes, refonte dispositions,
pipelines, consent, deduplication, and object intention. Removal is verified by authoritative
absence. A failed operation can be reopened only after stale pre-write/readback/comparison evidence
is cleared.

The packaged runtime intentionally uses the Python standard library only so the skill remains
executable without installing packages in an analyst environment. Draft 2020-12 JSON Schemas are
structural/editor aids and are meta-validated with the existing development-only `jsonschema`
dependency; the focused Python modules remain authoritative for cross-object, semantic, consent,
authorization, and lifecycle invariants that JSON Schema cannot express cleanly.

On failure, only the failed/uncertain operation and its transitive dependents stop. Independent safe
subtrees continue. A failed Client prevents its destination tags and cutover; an unrelated GA4
subtree need not stop because a Meta tag failed. Ambiguous writes are read before any retry, and
only documented non-applied rate limits retry within a bound.

Every mutation must link to an approved requirement and carry an exact, payload-hashed approval
record from that requirement's approved-input locator. A payload change invalidates that record;
authority still comes from the user's instructions and source material, never from a hash.
`official-current` documents mechanics but never authorizes a write. First-party `user_data` and
`user_id` configuration must be owned by an explicit first-party-data route. Shared Google
Configuration Settings changes require complete closure over all authenticated baseline consumers.
These are consistency and operational checks. They do not cryptographically authenticate user
approval, prove documentation relevance, or make editable local artifacts a security boundary.

Credentials are resolved through an ephemeral secret provider for mutation and never written to
the contract/run/diff/render/result. Readback may prove matching secret-field presence and all
non-secret fields, but reports `present-not-compared`; two redacted markers never prove value
equality.

## Acceptance And Result

Use `Configured`, `Partial`, `Blocked`, or `Deferred`. `Configured` requires complete target
baselines, authoritative readback, static cross-target invariants, and an identical-rerun no-op.
Open publication and recette dependencies do not downgrade a completed saved graph.

The human result and machine-readable run record describe configured targets, object changes,
field/consent/dedup mappings, saved readback, unresolved external dependencies, and the explicit
fact that runtime validation was not performed. Runtime recette independently uses the tracking
plan and live GTM/Preview evidence; it does not consume or trust a configure-gtm result artifact.

The external rollout sequence is server publication, server recette, web cutover publication, then
web and end-to-end recette. This repository never executes those steps.

## Boundaries

The skill does not design tracking plans, develop a site/dataLayer, provision cloud tagging
infrastructure or DNS/CDN, implement vendor APIs outside GTM, perform general audit/cleanup, run
browser/server recette, make legal decisions, administer vendor accounts, generate credentials,
publish, or create GTM versions.

Measurement Protocol, mobile-app, CRM, offline, and arbitrary backend ingress remain future
extensions.

## Repository Map

- `SKILL.md`: entrypoint, route classification, conditional playbook routing, and core rules.
- `references/01-orientation/`: utility contract and live official-source discipline.
- `references/02-execution/`: web playbooks plus conditional `pipeline/` and `server/`
  guidance.
- `references/03-judgement/`: saved-state acceptance and configuration-result guidance.
- `schemas/`: current contract 7.0 and run 4.0 schemas.
- `scripts/configuration_run.py`: current-only CLI over split validation/state/render modules.
- `scripts/adapter_runtime.py`: target registry, capability-local execution, redaction, and
  dependency containment.
- `scripts/diff_object_graph.py`: target-aware normalized graph comparison, including Clients and
  Transformations.
- `tests/`: current web, server/pipeline, security, adapter, schema, and
  documentation tests.

## Install And Validate

Install the release archive or copy `VERSION`, `SKILL.md`, `agents/`, `references/`, `schemas/`,
the packaged runtime scripts, and `LICENSE` into the target skill directory.

~~~powershell
python -m pip install -e ".[dev]"
python -m ruff format --no-cache --check scripts tests
python -m ruff check --no-cache scripts tests
python scripts/check_release.py --tag v10.0.0 --release-notes CHANGELOG.md
python -m unittest discover -s tests -v
python -m compileall -q scripts
python scripts/build_skill_package.py --output dist/configure-gtm-v10.0.0.zip
git diff --check
~~~

Releases use Semantic Versioning. Major versions may replace obsolete interchange contracts;
minor and patch versions evolve the current supported surface.
