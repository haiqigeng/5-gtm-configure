# Naming and reuse

## Contents

- [Follow type, owner, and purpose](#follow-type-owner-and-purpose)
- [Name source and destination independently](#name-source-and-destination-independently)
- [Reuse by semantic equivalence](#reuse-by-semantic-equivalence)
- [Prefer references over repeated literals](#prefer-references-over-repeated-literals)
- [Use lookup tables only when applicable](#use-lookup-tables-only-when-applicable)
- [Organize folders clearly](#organize-folders-clearly)
- [Add notes where they preserve non-obvious decisions](#add-notes-where-they-preserve-non-obvious-decisions)

## Follow type, owner, and purpose

Use an explicit analyst naming decision when supplied. Otherwise use the skill patterns below.
Preserve an existing container convention only as a presentation choice when it is consistent within
the relevant object family, clearly communicates type/owner/purpose, and does not weaken the skill
standard. Do not infer a global convention from a few legacy objects or let naming determine the
technical architecture.

| Object type | Pattern | Example |
| --- | --- | --- |
| Tag | Vendor - type - event/qualifier | `GA4 - Event - page_view`, `Meta - Event - Purchase` |
| Config/base tag | Vendor - Config | `GA4 - Config`, `Meta - Config` |
| Normal trigger | Trigger type - value | `CE - purchase`, `Click - newsletter_cta` |
| Blocking trigger | Block - CMP - vendor denied | `Block - Didomi - Meta denied` |
| DataLayer variable | DLV - actual source value/path | `DLV - ecommerce.items` |
| Constant | CST - semantic value | `CST - GA4 measurement_id`, `CST - currency` |
| Custom JavaScript | CJS - vendor - output | `CJS - Meta - contents` |
| Lookup table | LUT - purpose | `LUT - currency by hostname` |
| Regex lookup table | RLT - purpose | `RLT - environment by hostname` |
| Google settings variable | Vendor - setting type | `GA4 - Config Setting`, `GA4 - Event Setting` |

Keep vendor/platform first for tags and vendor-owned special settings. Keep variable type first for ordinary variables. Use snake_case for source event names and field-oriented values. Preserve official destination event casing when the vendor requires another form.

Use a short stable acronym only when the full type/vendor name is unwieldy and the container recognizes it. Do not invent prefixes such as `GCS` for GA4 configuration.

## Name source and destination independently

Name a DLV after the actual source key, including an intentional source typo if that is the real contract. Use the official destination name in the tag field, not in a misleading DLV rename.

Name a vendor transformation after its output, not its input. For example, use `CJS - Meta - contents` for the Meta-formatted result.

## Reuse by semantic equivalence

Select the target implementation from the applicable skill playbook and current official/template
documentation before adopting local patterns. Then inspect candidates and all their consumers.
Classify each candidate as:

- `conformant`: passes the selected reference architecture and every applicable static criterion;
- `conformant-with-naming-debt`: functionally conformant, with only harmless naming inconsistency;
- `nonconformant`: uses an outdated, brittle, over-complex, unsupported, or incorrect pattern;
- `conflicting`: would duplicate, suppress, broaden, or otherwise interfere with the target design;
- `unknown`: critical behavior or consumers cannot be established.

Reuse only `conformant` or `conformant-with-naming-debt` candidates, and only when these dimensions align:

- object type and terminal output;
- business and vendor ownership;
- data type, shape, and null behavior;
- source timing and event scope;
- normal and consent firing behavior;
- template/version and destination compatibility;
- environment/hostname scope;
- expected future change path.

Matching names or values alone are insufficient. Existing prevalence is not evidence of best
practice. Two IDs with the same current string can require separate constants when they belong to
different destinations or owners. Conversely, do not duplicate a fully conformant object merely
because its name is imperfect; reuse it and report naming debt unless renaming is authorized.

Do not reuse a nonconformant or unknown object. Do not add a clean parallel implementation around a
known conflicting tag, trigger, consent path, or automatic event. Update or disable the conflicting
object only when the authorized scope permits it; otherwise block the affected requirement and state
the exact decision needed. This is safe integration, not container cleanup.

## Prefer references over repeated literals

Use a constant or settings variable when it makes a stable value visible, reusable, and safer to change. Typical candidates include measurement IDs, pixel IDs, UET IDs, conversion IDs/labels, and a genuinely fixed currency.

Do not force a constant for every literal. Keep an event-specific value on the tag when a reference adds indirection without reuse or clarity.

## Use lookup tables only when applicable

Actively evaluate a LUT/RLT whenever multiple environments, hostnames, destinations, currencies,
event families, product groups, or other real inputs map deterministically. Create one when:

- multiple real input scenarios exist;
- the mapping is deterministic;
- default/no-match behavior is safe and explicit;
- it reduces duplication or clarifies environment/vendor mapping;
- representative cases can be tested.

Apply the same rule to analytics and media. Do not use a table for a single mapping or force unrelated scenarios together.

Never use a production analytics or media destination as the table's default/no-match result. Load
the multi-destination routing playbook when destination identity, environment, brand, region, or
consent varies; separate tags when a table would hide incompatible ownership or behavior.

## Organize folders clearly

Follow an existing folder model only when it is coherent and compatible with the selected
best-practice architecture. For a configuration that creates or owns several related objects,
create or reuse one shallow folder by vendor/platform or implementation workstream. Keep tags,
triggers, and variables together when one workstream owns them unless the coherent container model
separates object families.

Do not create a folder for one isolated object when it adds no clarity. Do not create deep nesting,
duplicate an equivalent folder, or move unrelated existing objects merely to make the workspace
look tidy; that is cleanup scope. Record the intended folder in the configuration map before
mutation and verify the saved folder reference.

## Add notes where they preserve non-obvious decisions

Use object notes/descriptions when supported to record a critical source event, vendor schema decision, consent exception, template dependency, or temporary blocker. Keep notes concise and free of client secrets or personal data.

Do not duplicate the entire configuration result inside every object.

## Name target ownership without duplicating semantics

Keep existing web naming defaults. For server objects, make the family and destination role clear,
for example `Client - GA4 - Web transport`, `EDV - transaction_id`, `Server - Meta - Purchase`, or
`Transformation - Meta - Item projection`. Use target-scoped semantic keys internally rather than
forcing target IDs into every visible name.

Reuse one compatible Client for a request class and one Event Data variable for an identical path;
do not create one Client per web tag. Use a shared endpoint Constant/LUT only when it provides real
reuse or environment routing, and LUT/RLT for deterministic routing rather than decorative
machinery. Keep folders shallow and destination-oriented. Never reuse a broad Transformation or
secret-bearing template merely because its name looks compatible.
