# Rule ownership and validation map

The runtime package has one command router and seven implementation concerns. Generate the full
maintained-file inventory, package membership, Python import graph, function calls/failure sites, schema constraint pointers, Markdown links,
word counts and per-file byte hashes
with `python tools/check_architecture.py --output ownership-map.json`. The release attaches that
map to the same tag as the archive. It includes repository-only tests, tools and workflow files.

## Data flow

Approved input enters `intake`; `contract.py` validates the resulting contract. The shared schema
loader checks structure before domain predicates inspect meaning. `ConfigurationGraph` projects
contract keys or durable run IDs once into the domain's operation graph. `runtime/state.py` owns
materialization and transitions; `runtime/engine.py` executes through the adapter protocol.
Adapters supply authenticated evidence and transport, while comparison owns native normalization.
The renderer reads durable evidence and the public state inspection to produce the human view.
It presents readiness/recovery without reclassifying operation state or dependency blockers.

Core imports core. Domain imports core and domain. Higher-level coordinators compose those layers.
Shared functions use public names; private functions belong to their defining module. The static
release gate rejects reversed core/domain dependencies, cycles and private cross-module access.

## Instruction ownership

The entrypoint routes work and summarizes the outcome. Core references own distinct decisions;
consumers link to the defining rule and add only their local application.

| Decision | Instruction owner | Consumers / deterministic counterpart |
| --- | --- | --- |
| Scope, priorities, target authority, boundaries | `references/core/authority.md` | workflow, authoring, feature guides; contract/domain authority validators |
| Source research, currency, discrepancy classification | `references/core/evidence.md` | product guides and authoring; evidence schema and domain checks |
| Task sequence and which owner to consult | `references/core/workflow.md` | SKILL entrypoint; CLI/runtime lifecycle |
| Declarations, field namespaces and mechanical compilation | `references/core/authoring.md` | feature guides; schemas, intake and domain fields |
| Writes, recovery, readiness, privacy and finalization transition | `references/core/execution.md` | adapter/pipeline guides; runtime and core privacy |
| Verdict meanings and human/machine handoff | `references/core/acceptance.md` | workflow, authoring and renderer |
| Source/destination mapping and runtime-data boundary | `references/data/mapping.md` | authoring and product guides; fields, shapes and native validators |
| Projection implementation and static input vectors | `references/data/transformations.md` | mapping and destination-specific projections |
| Adapter evidence/caching and quota mechanics | `references/adapters/custom.md`, `quotas.md` | execution and host guides; adapter/runtime implementation |
| Google field placement | `references/analytics/google-fields.md` | GA4, Ads and identity guides; native field registry/resolver |
| GA4 collection ownership | `references/analytics/ga4-ownership.md` | page views, automatic events, consent lifecycle; domain page-view predicates |
| Identity feature, source and hash lifecycle | `references/data/identity.md` | browser/server product guides; first-party-data domain checks |
| Web eligibility, lifecycle and product classification | `references/consent/web.md`, `lifecycle.md`, `product-capabilities.md` | product-specific signal guides; consent/execution predicates |
| Media declarations and product-specific application | `references/media/common.md`, `server.md`, `references/vendors/` | common owners linked from product guides; feature/native validators |
| Reuse, naming and destination selection | `references/organization.md`, `routing.md` | web/server resources; native graph and target validation |
| External rollout order | `references/pipeline/architecture-and-workflow.md` | acceptance and pipeline handoff; publication dependency records |

Product, consent, identity, web/server and routing guides retain their feature-specific mechanics.
Static checks verify links and code ownership; independent scenario review checks whether the
instructions guide the agent to the appropriate owner without losing required safeguards.

## Owners across the complete skill

| Rule or artifact | Primary owner | Consumers and supporting files | Validation owner |
| --- | --- | --- | --- |
| Discovery and task routing | `SKILL.md` | `agents/openai.yaml`, routed `references/` | `tools/check_release.py`, `tests/test_current_documentation.py` |
| Authority and approved scope | `domain/requirements.py` and `contract.py` | core authority references, contract and runtime validation | authority, contract and runtime tests |
| Closed record structure | `schemas/common.schema.json` | contract/run schemas, `core/schemas.py` | schema consistency, run schema, ownership invariant tests |
| Phase-specific record structure | contract/run schemas | cached core schema loader | schema and packaged release tests |
| Destination namespaces | `schemas/common.schema.json` field registry | importer, requirement validation, compiler, mappings and pipeline declarations | destination and schema parity tests |
| Enums, versions and state transitions | `core/model.py` | domain, state, verification; schema enum representations | schema consistency and release version checks |
| JSON values, typed access and canonical hash | `core/validation.py` | contract validation bindings, state, verification, comparison | ownership invariants and durable evidence tests |
| Secrets and public identifiers | `core/privacy.py`, `core/public_identifiers.py` | persistence, adapters, renderer | privacy and redaction shape tests |
| Approved GA4 delivery conversion | `intake/ga4.py` | analytics intake reference, producer delivery fixtures | GA4 intake and ownership invariant tests |
| Request compilation | `intake/request.py` | `comparison/inventory.py`, CLI prepare | request behavior and preparation inventory tests |
| Domain graph projection | `domain/context.py` | `contract.py`, `runtime/validation.py` | graph parity and contract/run scenarios |
| Target identity and localization | `domain/targets.py`, `domain/localization.py` | discovery, web domain coordinator | contract, web feature and adapter tests |
| Native fields and assertions | `domain/native.py`, `domain/fields.py` | payload mappings, comparison, verification | native, field and release field gates |
| Action semantics and resources | `domain/actions.py`, `domain/resources.py` | contract and runtime validation | contract, native inventory and execution tests |
| Consent and deduplication | `domain/consent.py`, `domain/deduplication.py` | web, server and pipeline validators; consent references | consent, predicate binding, shared event ID and dedup tests |
| Web execution and page views | `domain/execution.py`, `domain/page_views.py` | `domain/web.py`, `web_model.py`, `web_native.py` | execution, page-view and product-specific consent tests |
| First-party data and inventory consumers | `domain/first_party_data.py`, `domain/inventory.py` | web coordinator, identity and organization references | first-party, Google Ads and inventory tests |
| Server and pipeline predicates | `domain/server.py`, `domain/pipeline.py`, `domain/pipeline_declarations.py` | phase-neutral graph, pipeline and server references | pipeline, quota/identity and packaged scenarios |
| Dependency closure and external owners | `domain/graph.py` | contract, runtime and web validation | contract, pipeline and execution scenarios |
| Field ownership and dependency readiness | `runtime/readiness.py` | native namespace owner, state inspection, engine and manual checkpoints | shared consent/settings, all-blocked and native-owner tests |
| Durable state and evidence | `runtime/state.py`, `runtime/validation.py`, `runtime/verification.py` | run schema, CLI run | state, verification, recovery and run schema tests |
| Writes, recovery and quota discipline | `runtime/engine.py` | adapter protocol and adapters | execution, transport and quota tests |
| Host transport and discovery | `adapters/`, `scripts/mcp_relay.js` | MCP CLI commands and adapter references | MCP transport and SDK/relay fixtures |
| Native and semantic comparison | `comparison/` | preparation, conformance, runtime verification | native comparison, GA4 intake and conformance tests |
| Human report | `render.py` | acceptance reference, public state inspection and CLI run | blocker/recovery parity and report injection scenarios |
| CLI interface | `scripts/configure_gtm.py`, `cli/` | documented commands | CLI behavior and extracted-package help checks |
| Package and release | `tools/`, `.github/workflows/` | VERSION, pyproject, README, changelog | architecture, packaging and release tests |
| Reusable synthetic test graphs | `tests/support/`, `tests/fixtures/` | behavior-owner test modules | full suite; producer-bound fixture bytes remain unchanged |

## Review findings resolved by mechanism

| Finding | Root correction | Files carrying the invariant | Regression evidence |
| --- | --- | --- | --- |
| CG-64 | One enum owner; execution uses the same supported consent vocabulary | core model, domain execution/consent, common schema, consent web reference | product-specific contract-to-run scenario; duplicate-owner gate |
| CG-65 | Schema owns key sets and record types; Python owns cross-record meaning | all three schemas, core schema loader, contract/runtime validators, domain fields | unknown requirement and nested-record keys rejected; shared definition checks |
| CG-66 | One schema-owned destination model preserves every field; readiness blocks unresolved dependent operations | common field registry, intake GA4, domain fields/native/identity, runtime state | full delivery import, configuration User-ID/source/lifecycle proof, unresolved-field isolation and input preservation |
| CG-67 | One phase-neutral graph and feature-owned validators; public module boundaries | context/localization/targets, contract, runtime validation, web/server/pipeline, comparison inventory | both phase scenarios, import graph gate, recovery/forward tests |
| CG-68 | One canonical JSON hash function and representation | core validation/model, common schema, state/verification | Unicode/type/hash regression; current contract/run/verification schemas |
| CG-69 | Semantic link labels and derived CLI usage/version checks | references, router, release checker | stale-label synthetic regression; every packaged command help |
| CG-70 | Test files follow behavior owners; fixture graphs live in support | tests/support, behavior suites, architecture and ownership suites | all original test methods retained; branch coverage measured on both tags |
| CG-71 | Field ownership is distinct from inherited requirement attribution; blockers propagate through the operation graph | runtime readiness/state, native namespace owner, field binding validation | packaged two-event shared consent scenario; independent shared settings/configuration and recovery replay |
| CG-72 | Closed schema records own structural keys, including public declaration APIs; local copies are detected | common/run/contract schemas, core schema loader, runtime validation/state, field/consent/public-identifier APIs, architecture gate | existing malformed-record tests, independent schema probes, local two/five-key mutation tests |

## Limits of the checks

Static ownership analysis catches literal constant duplication, identical substantial function
bodies, unused top-level names, dependency direction and cycles. Closed-record key detection
compares complete literal sets of at least two keys with schema records, including function locals;
it does not detect partial key subsets or computed sets. Its reference analysis is
conservative; it does not prove semantic equivalence or identify every possible duplicate rule.
The inventory indexes every maintained file; function call/failure indexes are syntactic and may
include nested function sites. Composition and leaf constraints retain their exact schema pointers.
Schema validation owns structural correctness, while positive and negative behavior scenarios
exercise domain meaning. Coverage excludes child-process execution and is a lower bound.
Offline transports and saved-structure tests do not certify live GTM or vendor delivery.
