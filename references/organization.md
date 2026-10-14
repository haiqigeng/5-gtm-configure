# Naming and reuse

## Follow type, owner, and purpose

Use the explicit analyst naming choice, otherwise a coherent clear convention across the relevant
object family, otherwise these patterns. Naming presents the selected architecture.

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

Tags and vendor-owned settings lead with vendor; ordinary variables lead with type. Source events
and field values use snake_case while destination casing follows the official product. Stable
recognized acronyms can shorten unwieldy labels. A DLV names the actual source key, including a
contractual typo; a transformation names its destination output.

## Reuse by semantic equivalence

Select current reference architecture before evaluating existing candidates and all consumers.
Classify them as `conformant`, `conformant-with-naming-debt`, `nonconformant`, `conflicting` or `unknown`.
Reuse either conformant class when type/output, business/vendor owner, shape/missing behavior,
timing/scope, firing/consent, template/destination, environment and expected change lifecycle align.
Harmless naming debt can remain until an authorized rename.

Independent owners can require separate constants even for equal current strings. Conflicting or
unsupported existing paths require an authorized update/disable or a blocker on the affected
requirement. This integration decision applies to the requested scope.

## Prefer references over repeated literals

Constants/settings expose stable values where reuse or clarity justifies the reference. Event-specific
literals stay local when that is the clearest ownership. LUT/RLT represents multiple real deterministic
scenarios with explicit safe no-match behavior and representative tests.
[Routing](routing.md) owns destination/environment selection and compatible consumer boundaries.

## Organize folders clearly

Reuse a coherent folder model or one shallow vendor/workstream folder for related owned objects.
Keep its tags/triggers/variables together unless the compatible existing model separates families.
An isolated object can remain without a new folder. The approved organization scope determines
membership; record and verify native folder references.

## Preserve non-obvious decisions

Concise supported notes capture material source, schema, consent, template or blocker decisions.
The run remains the complete result; notes follow its privacy rules.

## Name target ownership without duplicating semantics

Server names identify family/destination, for example `Client - GA4 - Web transport`,
`EDV - transaction_id`, `Server - Meta - Purchase`, `Transformation - Meta - Item projection`.
Internal semantic keys carry target scope. Reuse compatible Clients per request class and Event
Data variables per identical path under the same equivalence analysis, including Transformation
consumer scope and secret/template ownership.
