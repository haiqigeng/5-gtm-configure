# Tracking-plan fidelity and conformance

## Contents

- [Keep measurement design outside configuration](#keep-measurement-design-outside-configuration)
- [Separate approved semantics from GTM implementation](#separate-approved-semantics-from-gtm-implementation)
- [Resolve the relevant source scope](#resolve-the-relevant-source-scope)
- [Classify official-documentation discrepancies](#classify-official-documentation-discrepancies)
- [Resolve discrepancies before mutation](#resolve-discrepancies-before-mutation)
- [Prove exact conformance](#prove-exact-conformance)
- [Use the deterministic comparator](#use-the-deterministic-comparator)

## Keep measurement design outside configuration

Implement an approved analytics tracking plan faithfully. Do not rename or substitute an event, add
or remove a parameter, add a literal, change a source, alter a business filter or success moment, or
broaden scope because another measurement design appears better.

The tracking-plan analyst or tracking-plan skill owns measurement design and optimization. This
skill owns official technical validation, clean GTM architecture, actual workspace mutation, and
saved-state verification. Use a later analyst decision only after it explicitly amends the approved
input.

Use current official documentation to validate classification, requirements, types, shapes, limits,
and implementability. Documentation may prove that a choice is invalid, reserved, deprecated,
missing a required field, incompatible, or unsupported. It does not authorize silent optimization
or payload enrichment when the approved choice remains valid.

Apply the same fidelity rule to an exact direct analytics requirement. When the user supplies only
an informal business action without an approved event, fields, source event, and timing, request the
analytics decision rather than silently creating a measurement plan.

Keep media separate: an explicit media brief establishes its objective and current official media
documentation establishes its destination schema.

## Separate approved semantics from GTM implementation

Treat these as approved analytics semantics:

- included business requirements;
- destination event and classification;
- outgoing event, item, user-property, and other payload fields;
- literals, source paths, approved transformations, and missing-data behavior;
- source event, success moment, repeatability, and business filters.

Treat these as GTM implementation choices when they do not change semantics:

- account, container, workspace, destination identity, tag type, and installed template;
- GTM variables, DLV version, folders, and object references;
- normal and blocking triggers that reproduce the approved timing and policy;
- consent settings, firing options, sequencing, priority, and template mechanics;
- adapter actions, pagination, fingerprints, mutation order, and saved-state verification.

An official requirement missing from the tracking plan is not infrastructure. If it is technically
required, classify the analytics requirement as a blocking discrepancy instead of inventing it.

## Resolve the relevant source scope

When the supplied workbook or artifact contains multiple relevant parts, classify only what can
affect the requested configuration as:

- `included`, with a stable requirement ID and source reference;
- `reference-only`, such as a dictionary or example;
- `excluded`, with the approved reason;
- `ambiguous`, with the exact decision needed.

Visibility is evidence, not authority: a hidden sheet may be approved and a visible sheet may be a
reference or legacy artifact. Do not turn this targeted scope resolution into a tracking-plan audit.
Block only ambiguous dependent requirements when other requirements remain independently safe.

Translate each included requirement into the concise operational configuration map. Preserve the
source sheet/cell or row reference needed to prove exact conformance; do not require a universal
spreadsheet parser or create a large secondary plan.

Prefer an immutable requirement ID supplied by the approved plan. Otherwise derive one once from
the exact source locator and business action, for example `TP::Events::12::generate_lead`, and keep
it stable across sorting, mutation, readback, and recette handoff. The packaged run initializer
ingests a validated configuration contract and preserves these IDs; it deliberately does not guess
the layout or meaning of an arbitrary workbook.

## Classify official-documentation discrepancies

Use exactly one class for each real difference:

| Class | Meaning | Behavior |
| --- | --- | --- |
| `blocking-error` | The requested collection is invalid, reserved, missing a required field, type/shape incompatible, unsupported, or impossible to map safely. | Do not mutate the affected requirement. Give the exact official evidence and amended decision needed. |
| `advisory` | The approved collection remains technically valid, but current documentation identifies a recommended event, field, or convention that may be more appropriate. | Report it and implement the approved contract unchanged by default. |
| `implementation-note` | Documentation determines a GTM/template setting without changing collection semantics. | Apply the documented setting within the configuration. |

Never misclassify an optional or recommended field as required, and never downgrade a genuine
required-field or reserved-name conflict merely to finish the tag.

## Resolve discrepancies before mutation

Before the first affected write, provide only the concise discrepancy information needed for the
analyst to understand the outcome: requirement, approved value, current official finding, class,
impact, source, and default action.

- Continue unchanged for an advisory unless the analyst explicitly amends the plan.
- Stop the affected requirement for a blocking error.
- Continue unaffected requirements only when their dependencies are independent and the saved
  partial graph cannot mislead or conflict.
- Repeat unresolved blocking items in the handoff.

No separate approval table is needed when the comparison is conformant and no material decision is
required.

## Prove exact conformance

Before mutation, compare the approved analytics semantics with the intended event tags. After
mutation, compare them with authoritative saved workspace fields. Require:

- identical included requirement IDs;
- identical destination and source event names;
- identical business timing, repeatability, and filters;
- exact parameter/property/item-field set equality;
- exact approved source path or literal for every outgoing field;
- zero unauthorized additions, removals, substitutions, or hidden-scope inclusions.

Keep technical infrastructure outside the collection comparison. IDs, folders, triggers, consent,
references, and template mechanics are required implementation fields but are not analytics payload
enrichment.

A zero-difference intended result may proceed. Any non-zero semantic difference must be corrected,
classified as a blocking discrepancy, or supported by an explicit amended analytics decision. A
zero-difference saved result is required for `Configured`.

## Use the deterministic comparator

Use `scripts/validate_contract_conformance.py` when the approved, intended, or saved contracts can be
represented as normalized JSON. The agent interprets the client artifact; the script verifies exact
equality and never guesses workbook semantics.

Each JSON document contains:

- `scope`, normally with `included`, `reference_only`, and `excluded` collections;
- `requirements`, a list of objects with unique stable string `id` values;
- collection-semantic fields, with `parameters` represented as a mapping when parameter order is
  irrelevant.

Requirement and scope-list order is non-semantic. Nested arrays within a requirement remain
order-sensitive. Adapter and repository metadata may remain outside `scope` and `requirements` and
is ignored deliberately.

Run before and after mutation:

~~~powershell
python scripts/validate_contract_conformance.py --approved approved.json --candidate intended.json
python scripts/validate_contract_conformance.py --approved approved.json --candidate saved.json
~~~

Exit code `0` means exact conformance, `1` means a deterministic difference, and `2` means invalid
input or invocation. Preserve the concise JSON result with the implementation evidence.
