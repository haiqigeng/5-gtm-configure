# Release 13.0 evaluation

Evaluated 2026-10-14 against the published v12.0.0 commit
`e7de177788e5fd8a263b2f611062ccd379784712`. The baseline was archived before edits.
The final assessment is **ready for an authorized field test, with no known reproducible blocker
in the exercised offline workflows**. It is not a claim of universal correctness or live certification.
The user explicitly deferred live GTM testing; no live calls, workspace writes or publication occurred.

## Complete map and ownership

The maintained tree has 268 files, including 58 runtime Python modules; the installable archive
contains 153 files. [The ownership matrix](architecture.md) maps every concern to its implementation,
schema, instructions and behavioral tests. Generate the detailed index with:

```shell
python tools/check_architecture.py --output ownership-map.json
```

The release attaches that index. Every maintained file has package membership, layer, byte size
and SHA-256. Python entries expose imports, definitions, function calls and failure sites. Schema
entries expose structural/composition constraints and references at exact JSON pointers. Markdown
entries expose word counts and links. Repository tests, tooling and workflows are included.
The index is a static navigation aid; syntactic calls and failure sites do not prove semantics.

The schema owns record structure and the field-namespace registry. Domain modules own relational
meaning. Contract and durable-run coordinators consume the same domain graph. Preparation derives
mechanical facts; runtime state owns readiness and transitions; adapters own transport; comparison
owns exact JSON equality; rendering consumes evidence. The release gate enforces dependency direction,
private-module boundaries, cycles, duplicate definitions/constants, unused definitions and stale labels.

## Mechanisms corrected

| Mechanism | Root correction | Behavioral proof |
| --- | --- | --- |
| Destination loss or import dead-end | One schema field registry drives importer, compiler, mappings and pipeline declarations. All approved fields survive import. | Unchanged delivery imports 3 requirements / 14 fields; every source, destination, type, nullable/conditional value and clear timing independently reconciled. |
| User-ID configuration | `configuration_fields.user_id` maps to the authorized Google configuration namespace, exact source and approved lifecycle. | Contract, preparation, run and synthetic saved-state verification pass; wrong namespace/source/transformation/lifecycle fails. |
| Native field ambiguity | One exact collection-field resolver handles event/configuration tables and shared settings. Control aliases remain separate. | Case, punctuation and whitespace substitutions fail; shared inheritance, local overrides, duplicates, cycles and wrong variable types tested. |
| Unknown destination readiness | `unresolved_fields` preserves the field and blocks its dependent operations through the same readiness predicate used by checkpoints. | Zero affected writes; independent folder operation still verifies; manual checkpoints cannot bypass the predicate. |
| Conformance validity | Both semantic projections use the shared closed requirement schema, scope and route rules before comparison. | Identical invalid input, misspelled keys, unsupported routes and inconsistent scope reject; valid ordered semantics compare correctly. |
| Evidence type equality | Saved comparisons and rendered changes use type-strict JSON differences. | Boolean-to-number substitution in durable evidence rejects. |
| Standalone server workflow | The Client fixture carries its native-bound claim assertion and ships in the packaged suite. | CLI preparation, contract validation, conformance and durable initialization succeed. |
| Preflight reporting | Workspace changes derive their wording from baseline completeness. | Unknown baseline reports `not inspected`; inspected empty baseline reports `none`. |

These replace or generalize existing mechanisms. No compatibility modules, schema migrations,
new runtime dependencies or additional SKILL.md rules were added. Contract 10.0 and run 8.0 are
current; verification remains 2.0. Producer artifact bytes and hashes are unchanged. The installed
tracking-plan producer still emits handoff 2.0.0 / canonical plan 6.0.0, matching the importer;
producer release labels are provenance rather than input-schema gates.

## Evaluation gates

| Aspect | Evidence and result |
| --- | --- |
| Structural validity and ownership | Architecture, schema, routed links/anchors, stale labels, CLI help, package and version gates pass. Skill-creator frontmatter/scaffolding check passes. |
| Repository reliability | 482 tests and 508 subtests pass with relay tests required and none skipped. The fresh v12 baseline passes 459 / 508 under the same environment. |
| Packaged usefulness | 29 self-contained tests pass from the extracted archive, including web, pipeline, folder and standalone Client inputs. |
| Independent forward test | Four complete CLI workflows pass prepare/validate/conformance/init/inspect/render. Delivery fidelity and 18 independent native mapping checks pass. |
| Recovery and completion | Six independent adapter scenarios verify convergence, no-write pre-write drift, lost-reply recovery, durable uncertainty without duplicate writes, and reopening on final drift. |
| Error classification | Same 16 injected error cases produce identical v12/v13 behavior. Structured rate limits retry with simulated waits; ambiguous write failures remain uncertain. |
| Privacy | 18/18 leak canaries and 5/5 control cases pass. Four real local exports, 614 distinct GTM objects, have identical flagged results on both versions; no non-secret cookie-setting overblock. |
| Public identifiers | The legacy low-level canary still flags two undeclared browser keys. It supplies no public-identifier evidence. Current evidence-bound public-key tests pass; unknown key semantics remain conservatively blocked. No broad key allowlist was introduced. |
| Report integrity | Injection probe creates no forged summary section or live link. Preflight and incomplete operations make no Configured claim. |
| Coverage | Same branch-enabled harness: line coverage 80.79% to 81.20%; branch coverage 72.97% to 73.56%. Child-process execution is excluded, so these are lower bounds, not certification. |
| Context cost | SKILL.md is byte-identical. The six mandatory core documents total 7,041 words versus 6,974 (+0.96%); conditional guidance remains routed. |
| API and local cost | Large-container task: 51 calls on both versions. 20 events: 63 calls, 40 writes, 18 list pages, 521 KiB run on both versions. Local compute 2.0 s baseline / 1.9 s candidate; one synthetic timing sample, no speedup claim. |
| Package | 153 files, 396,926-byte ZIP versus 394,588 bytes in v12 (+0.59%). Deterministic rebuild and extracted-file checks pass. |

Final local archive SHA-256:
`3fafbe6ab01a640e882de8993753a312f3da4c967e0e7404a840dd50395bc1e4`.
The published checksum and installed bytes are checked separately during release installation.

## Remaining decisions and field-test boundary

`ga4_user_id` is no longer an unsupported importer destination. It is a configuration setting,
consistent with [Google's User-ID implementation guidance](https://developers.google.com/analytics/devguides/collection/ga4/user-id?platform=websites).
The approved source, consuming Google tag, consent and identity lifecycle must still be supplied.
The delivery alone does not authorize a target workspace or invent its native implementation.

`other` is intentionally unspecified input. The analyst must approve the actual destination surface
in revised requirements; preserve the original delivery and amendment as evidence. That decision
is outside measurement configuration's authority. Independent requirements can continue.

Non-scalar fields and unsupported native/template structures remain inspected agent-review mappings.
An approved lifecycle declaration does not prove actual authentication/logout behavior. Offline
checks do not prove live authentication, GTM persistence, template runtime behavior, browser/server
transport, vendor receipt, concurrency under a live host, or runtime recette. Those are the next
field-test subjects after explicit test-workspace authorization.

Raw local logs, immutable baseline, probe outputs, coverage JSON, detailed candidate map and
independent reproduction scripts are kept in `configure-gtm-evaluation-2026-10-14` outside the package.
No private container payloads or user filesystem paths are committed to the repository.
