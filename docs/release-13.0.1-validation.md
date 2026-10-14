# Release 13.0.1 evaluation

Evaluated 2026-10-14 against frozen v13.0.0 commit
`770730a8aa14fcf1b8185d495d9f1bba40a4f367`, following the independent CG-71/CG-72 audit.
The result is **ready for an authorized field test, with no outstanding reproduced defect in the
exercised offline scenarios**. Live GTM testing remains deferred by the user; no live calls,
workspace mutations or publication were performed.

## Complete mapping and ownership

The maintained tree contains 271 files and 59 runtime Python modules; 155 files are packaged.
The [ownership matrix](architecture.md) maps instructions, schemas, runtime owners and tests.
`python tools/check_architecture.py --output ownership-map.json` generates the release attachment:
every maintained file, package membership, byte hash, Python import graph, definitions, calls and
failure sites, exact schema constraint/reference pointers, Markdown links and word counts.

The whole-tree scan followed record definitions into direct public APIs, not only the reported
operation validator. Runtime header, target, operation, baseline capture, pagination, final inventory,
idempotency, baseline-error and observation checks now use their schema-owned structure. Mutation
approval retains its semantic projection equality. Public identifiers, native field bindings and
consent path declarations use the shared definitions. Public identifier, capture, pagination and
native field-path schemas have one definition with references from their consumers.

The static gate detects complete literal closed-record key sets of at least two fields, including
function locals. Two-key and five-key planted copies fail. A partial subset or computed set is
outside that check; the original audit's two-key subset of the much larger operation schema is not
claimed as detected. Dependency direction, cycles, private access, stale labels, unused definitions
and duplicate constants/functions remain checked.

## Root mechanisms corrected

| Finding | Correction | Evidence |
| --- | --- | --- |
| CG-71: inherited requirement labels block shared dependencies | One readiness graph distinguishes field ownership from requirement attribution. Shared dependencies remain usable when they serve a ready requirement. | The original reproduction changes from zero writes to two justified writes; no unresolved owner is written. |
| Shared native configuration ownership | Supported native namespaces select unbound owners before terminal-consumer inference; explicit bindings identify their owner directly. | A blocked shared Google setting holds the Google tag and both dependent event tags, with identical outcomes for inferred and explicit ownership. |
| Invalid blocked binding bypass | Owner, requirement, native namespace and exact field identity are validated at every status; mapped-value proof follows separately. | Wrong requirement, namespace, field, unknown owner, paused owner and variable owner reject. |
| Blocked work reported as waiting | Originating field/failure reasons propagate through dependencies; waiting means a dependency can still complete. | Transitive failed/uncertain/skipped dependencies show blockers. Partial runs and manual checkpoints agree. |
| CG-72: duplicated structural lists | Phase schemas and shared definitions own record structure; direct declaration APIs consume the same definitions. | Existing malformed-record suite plus 30 independent direct-API probes pass; local schema-copy mutation tests fail as intended. |

This replaces the old readiness mechanism and structural copies. No SKILL.md rules, compatibility
facades, migrations or runtime dependencies were added. Contract 10.0, run 8.0 and verification 2.0
remain current. Producer delivery fixtures are byte-identical to v13.0.0.

## Re-audit and regression gates

| Aspect | Result |
| --- | --- |
| Repository suite | 507 tests and 508 subtests pass, with relay tests required and none skipped. Frozen v13.0.0 passes 482 tests and 508 subtests under the same environment. |
| Installed-package suite | 32 tests pass from the extracted archive, including the two-event shared-consent scenario. Zero, one and two blocked requirements produce seven, five and zero writes respectively. |
| Independent forward evaluation | Seven authored shared-consent/settings/configuration and recovery scenarios pass. The evaluator reproduced two defects in an intermediate candidate; both were fixed and the exact negative inputs replayed successfully. |
| CLI and validation boundaries | Five valid requests pass prepare, contract validation, init, run validation, inspection and rendering. Two invalid-owner requests reject before initialization. Six schema/semantic probes and 30 direct declaration API probes pass. |
| Recovery | Lost reply recovers through readback without duplicate writes; definite shared-variable rejection blocks dependents, and explicit reopen resumes only the ready branch. The same 16 injected error cases produce byte-identical baseline/candidate results. |
| Privacy | 18/18 leak canaries and 5/5 controls pass. Two undeclared public-browser-key cases retain the baseline conservative rejection; current evidence-bound public identifier tests pass. No new allowlist was introduced. |
| Real local exports | Separate processes scan the same four exports / 614 distinct objects: three objects flagged on both releases; zero flagged solely for non-secret cookie settings. Only aggregate results were retained. |
| Report integrity | Zero forged summary sections or live links in the injection probe. Incomplete graphs remain Partial/Blocked and checkpoint attempts cannot bypass unresolved fields. |
| Coverage | Same branch-enabled harness: line coverage 81.20% to 81.49%; branch coverage 73.56% to 73.99%. Child-process execution is excluded. The instrumented run exposed a stale test release label, corrected to read the release owner; the final non-instrumented full suite passes. |
| Architecture and skill structure | Architecture, schema, routed links, stale labels, CLI help, release metadata, formatting, lint and skill-creator validation pass. |
| Context cost | SKILL.md is byte-identical. The same entrypoint plus five mandatory core references total 8,220 regex-counted words on both tags. Only conditional maintenance guidance changes. |
| Remote/local cost | Large-container task remains 51 calls. Twenty events remain 63 calls, 40 writes, 18 list pages and a 521 KiB run. One same-input local sample is 2.0 s baseline / 2.1 s candidate; this is not a speed claim. |
| Package | 155 files; 400,480-byte deterministic ZIP, versus 396,926 bytes in v13.0.0 (+0.90%). The extra runtime module isolates readiness; the extra fixture makes shared-consent behavior independently testable after installation. |

Local archive SHA-256:
`5526404f02704eca00360f249819cc8123bb842d1f1369339aee756713a6ce76`.
Published asset checksums and installed file equality are verified during release installation.

## Remaining input decisions and field-test boundary

`ga4_user_id` remains supported as a Google configuration field with an approved source, owner and
identity lifecycle. `other` remains an unspecified destination in the approved input: it needs an
approved destination decision, not an invented event parameter. That unresolved business decision
blocks its owning branch while independent ready requirements can proceed.

Offline checks do not certify live authentication, GTM persistence, actual consent or identity timing,
external template behavior, concurrent production hosts, browser/server transport or vendor receipt.
Non-scalar and unsupported native mappings still require inspected agent review. Those limits belong
to the authorized field test; there is no claim of universal bug freedom.

Raw logs, frozen baseline, package, coverage, complete maps, independent inputs and before/after
failure evidence are retained in the local `configure-gtm-cg71-evaluation-2026-10-14` audit folder.
Private exports and local user paths are excluded from the repository and package.
