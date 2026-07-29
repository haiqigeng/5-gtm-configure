# Analytics tags

## Contents

- [Use the analytics requirement as the business contract](#use-the-analytics-requirement-as-the-business-contract)
- [Configure the Google tag deliberately](#configure-the-google-tag-deliberately)
- [Resolve Google tag and destination identity](#resolve-google-tag-and-destination-identity)
- [Apply the GA4 safety gate](#apply-the-ga4-safety-gate)
- [Keep page view separate by default](#keep-page-view-separate-by-default)
- [Configure events from the official schema](#configure-events-from-the-official-schema)
- [Use native GA4 ecommerce mechanics](#use-native-ga4-ecommerce-mechanics)
- [Reconcile Enhanced Measurement and manual events](#reconcile-enhanced-measurement-and-manual-events)
- [Govern user properties and identifiers](#govern-user-properties-and-identifiers)
- [Configure lifecycle and diagnostic fields explicitly](#configure-lifecycle-and-diagnostic-fields-explicitly)
- [Record external Google and GA4 administration](#record-external-google-and-ga4-administration)
- [Apply consent](#apply-consent)
- [Verify the saved analytics setup](#verify-the-saved-analytics-setup)
- [Naming examples](#naming-examples)

## Use the analytics requirement as the business contract

Treat an approved tracking plan or exact direct analytics requirement as the authorized collection
contract. Implement its in-scope event names, outgoing fields, literals, source mappings, and business
timing faithfully. Use current official documentation to validate classification, appropriateness,
requirements, types, shapes, limits, and template feasibility; do not silently optimize the plan.

For each event, map:

| Requirement layer | Required decision |
| --- | --- |
| Business action | Confirm the exact success moment and intended analysis. |
| Source event | Use the exact approved source event and timing. If an approved direct requirement authorizes a new source contract, default to one vendor-neutral dataLayer Custom Event. |
| Source values | Verify key, event timing, type, cardinality, and sample output. |
| GA4 event | Use the exact approved event when technically valid. Report an applicable automatic, enhanced-measurement, recommended, or ecommerce alternative as advisory; never substitute it automatically. |
| GA4 parameters | Use the exact approved parameter set and validate official names, types, and item/event scope. A missing required parameter blocks; a missing recommended/optional parameter is not permission to add it. |
| GTM variables | Reuse or create DLVs, constants, settings, tables, or documented transformations. |
| Consent | Apply strict/basic CMP blocking by default; route explicitly approved advanced Google Consent Mode separately. |

Never copy a source key into GA4 merely because the names look plausible. Map the source field deliberately to an official destination parameter or an approved custom parameter.

If current documentation shows that the approved analytics contract is invalid, reserved, missing a
required field, type/shape incompatible, unsupported, or impossible to map safely, stop the affected
requirement and report the exact discrepancy. If the approved custom event remains valid while a
recommended event appears more appropriate, report the consequence before mutation and preserve the
custom event by default. Measurement redesign belongs to the tracking-plan analyst or tracking-plan
skill.

## Configure the Google tag deliberately

Use current Google documentation to distinguish:

- the Google tag/configuration tag;
- a Google tag Configuration Settings variable;
- a Google tag Event Settings variable;
- GA4 event tags and event-specific parameters;
- settings managed in the GA4 data stream or Google tag destination UI.

Inspect the actual installed/native tag fields and current connected destinations before designing
or updating settings. Do not configure a field because it exists in a newer documentation surface
when the target container cannot store or apply it.

Use these naming patterns unless the analyst supplies an explicit naming decision or the relevant
object family has a consistent, equally clear presentation convention. Naming compatibility never
changes the selected technical architecture:

| Object | Name |
| --- | --- |
| Primary Google tag | `GA4 - Config` |
| Qualified Google tag | `GA4 - Config - main` |
| Configuration Settings variable, when justified | `GA4 - Config Setting` |
| Event Settings variable, when justified | `GA4 - Event Setting` |
| Measurement ID constant | `CST - GA4 measurement_id` |

Reference the measurement ID through a compatible constant rather than hard-coding it repeatedly. Do not create a settings variable merely because GTM offers one.

Use a Configuration Settings variable only for a coherent set of configuration-level values reused across applicable Google tags. Use an Event Settings variable only for a coherent set of event parameters or user properties genuinely shared across applicable events. Keep transaction, item, search, form, and other event-specific values on the event tag.

Inspect consumers before changing either settings variable because one edit may affect many tags and destinations.

Use this semantic decision matrix; do not apply a fixed numerical threshold:

| Decision | Keep directly on tag | Use shared settings variable |
| --- | --- | --- |
| Ownership | Event-specific or independently owned | Same owner and change lifecycle across every consumer |
| Value/source | Transaction, item, form, search, or other event-specific value | Identical source or literal with identical type and missing behavior |
| Consent/destination | Different route or destination behavior | Compatible consent route and destination behavior |
| Change risk | A change should affect one event | A change intentionally should affect every enumerated consumer |

For multiple streams, properties, regions, or environments, load the multi-destination routing
playbook. Never place a production measurement ID as a lookup default.

## Resolve Google tag and destination identity

Do not use `Google tag`, `GA4 configuration`, `measurement ID`, and `destination` as synonyms.
Read the current saved fields and Google administration surfaces before mutation:

- `GT-...` identifies a Google tag;
- `G-...` identifies a GA4 web data stream and is the measurement ID used by GA4 Event tags;
- `AW-...` identifies a Google Ads destination and may also identify the Google tag used by that
  product;
- a destination receives data from a Google tag but is not itself another executable GTM tag;
- one Google tag can have connected destinations and inherited settings that affect more than the
  label visible on the GTM object.

For every Google execution unit, record the saved tag ID, every connected destination, the ID used
by each event tag, inherited configuration/event settings, and all consumers. Do not point a GA4
Event tag at a `GT-...` value merely because the Google tag UI displays it; use the exact current
GA4 measurement-ID contract. Do not create a second Google tag when connecting or reusing a
destination is the documented compatible architecture, and do not connect or remove a destination
without explicit authority because that changes routing outside one event tag.

## Apply the GA4 safety gate

Load `ga4-collection-safety.md` for every Google tag or GA4 event. Before mutation, validate current
official names, reserved prefixes, required fields, types, limits, final outgoing parameter/user-
property counts, item scope, and PII risk. Count inherited Event Settings fields as part of each
event's outgoing payload.

Classify a valid recommendation difference as advisory and preserve the approved contract. Stop an
invalid or unsafe requirement. Never silently truncate a value, coerce a type, delete a parameter,
or add a field to remain within a limit.

## Keep page view separate by default

When page-view configuration is in the approved scope, keep the Google tag from sending an automatic page view by default. Verify the current `send_page_view` behavior and set it to `false` only where a separately managed page-view event is required. Do not alter an existing compatible page-view architecture merely to impose this preference during an unrelated event change.

When the approved requirement includes a manually managed page view and no compatible tag already supplies it, create `GA4 - Event - page_view` with the approved source values and trigger. Before doing so:

1. Inspect existing Google tags and any supplied evidence of hard-coded or partner installations; record unknown outside-container installation as an external dependency.
2. Inspect Enhanced Measurement page-load and browser-history behavior.
3. Disable or avoid overlapping automatic behavior.
4. Verify page-load and SPA navigation semantics separately.
5. Design CMP timing so the initial page view is not lost or duplicated.

If the normal `page_view` dataLayer event occurs before CMP state is ready under strict/basic gating, use the CMP's officially documented one-time readiness event and a verified vendor gate. Do not use a repeatable consent-change event without an explicit duplicate and late-consent policy.

When the tag fires on a CMP event instead of the original `page_view` event, revalidate every page parameter at that later event. Use browser built-ins or retained dataLayer state only when the approved source contract establishes that the value is current and in scope; never assume an earlier event-scoped payload remains available. If a required value is missing or stale under the contract, block the page-view implementation and request a CMP-safe application event or source contract.

## Configure events from the official schema

For each GA4 event:

1. Open the current GA4 event reference.
2. Confirm automatic, enhanced-measurement, recommended, ecommerce, or custom classification and compare it with the approved event without substituting it.
3. Extract each parameter's exact name, requirement status, type, scope, cardinality, and limits.
4. Compare the approved parameter set with required, recommended, optional, and conditional findings. Block a missing required field; report other differences as advisories and preserve the approved field set.
5. Validate event-level and item-level placement.
6. Map each approved destination parameter to a named GTM variable or documented transformation.
7. Validate a representative resolved event, including all ecommerce items.
8. Prove exact approved-to-intended and approved-to-saved event/parameter equality.
9. Retain the current official-source manifest and approved locator for every outgoing field.

When a source key is misspelled, verify that the approved source contract uses that exact key. Name the DLV for the actual source key, then map it to the correctly spelled official GA4 parameter. Do not propagate source typos into destination fields.

Treat `value` and `currency`, transaction identifiers, and `items` according to the exact event reference. Never infer an item parameter from a similarly named event parameter.

## Use native GA4 ecommerce mechanics

For an approved GA4 ecommerce event, inspect the current GA4 Event tag's native ecommerce controls
before creating variables or transformations. Prefer the native `Send Ecommerce data` route when
the saved tag surface supports it:

| Source contract | Configuration |
| --- | --- |
| Event push contains the current GA4-shaped `ecommerce` object | Select the native Data Layer source and map only approved event-level fields that are not supplied through that object. |
| Approved object exists at another exact source path or needs an approved reusable projection | Select the native Custom Object source and reference that object variable. |
| Source is not GA4-shaped | Use direct field mappings or the narrowest real shape transformation; do not add a Boolean payload-eligibility helper. |

Preserve zero, false, one item, and every approved item. An empty or absent runtime object is a
site/dataLayer or recette dependency, not permission for this skill to invent `CJS - Ecommerce -
Eligible`, filter items, or suppress the tag. A design-time missing required mapping still blocks
configuration.

When persistent ecommerce state could leak into a later event, record that risk and the required
site/dataLayer clearing contract (commonly an `ecommerce: null` push before the next ecommerce
object). This skill does not insert a browser-side clearing script to compensate for application
state. Configure only the approved ecommerce events; an official funnel catalogue is not
authorization to add the rest of the funnel.

## Reconcile Enhanced Measurement and manual events

Inspect the target stream's confirmed Enhanced Measurement settings and the current Google tag
before adding a manual GA4 event. At minimum reconcile page views/history, scrolls, outbound clicks,
site search, video engagement, file downloads, and form interactions when the approved requirement
overlaps them.

| Situation | Configuration decision |
| --- | --- |
| Confirmed automatic event exactly satisfies the approved contract | Reuse that owner; do not add a duplicate manual tag. |
| Approved manual event must own collection | Configure the manual event and record the exact external Enhanced Measurement setting that must be disabled or narrowed. |
| Property-side state is unknown and collision is material | Block the affected mutation or record an explicit external dependency; do not assume either state. |
| Automatic event differs in timing or semantics | Preserve the approved contract and document why the two events are distinct or why one owner must change. |

## Govern user properties and identifiers

Add a user property only when it is explicitly approved, stable, has a valid analysis use, and current GA4 documentation permits it. Never add one merely because the source dataLayer exposes it. Keep it in an Event Settings variable only when it genuinely applies across the intended events.

Treat `user_id` as a separately approved Google tag configuration contract, not a routine event
parameter, user property, or custom dimension. Omit it while the user is not signed in, set the
stable approved non-PII identifier when authentication state is established, and send `null` when
the approved logout/reset event must clear a previously set value. Establish source, lifecycle,
consent, persistence, and every consuming Google tag before configuration. Configure `user_id`
directly on one consuming Google tag; use a Configuration Settings variable only when the same
contract is genuinely reused by multiple compatible Google tags. Keep `user_id`, GA4
user-provided data, and user properties as separate features with separate owners and scopes.

Configure approved user properties separately from `user_id`. Record their stable analysis purpose,
source, scope, limits, and reset behavior. Treat content groups as explicit approved configuration
fields with their own source and timing; do not infer them from URL structure or exposed data.

Do not send personally identifiable information to GA4. Do not repurpose media advanced-matching fields as GA4 parameters or user properties.

## Configure lifecycle and diagnostic fields explicitly

- Use `traffic_type` only as the collection-side value that supports an approved internal/developer
  traffic design. The GA4 Admin data filter that acts on it remains an external dependency and is
  never implied by the GTM field alone.
- Set `debug_mode` only for an approved diagnostic route. To disable it, omit the parameter from
  production collection; do not assume a literal `false` disables DebugView classification.
- Keep environment lookup behavior explicit and never route an unknown/no-match environment to a
  production measurement ID.
- Record default, authenticated, logout/reset, and environment transitions whenever a persistent
  configuration field can outlive the event that set it.

## Record external Google and GA4 administration

For every collected field or event, determine whether the approved reporting use also requires work outside the authorized GTM change. Record, without silently changing:

- GA4 custom dimensions or metrics for custom event, item, or user fields;
- GA4 key-event designation;
- data-stream or Enhanced Measurement settings that can duplicate or alter the selected event;
- Google tag destinations, shared settings, cross-domain configuration, unwanted-referral handling, or other current administration surfaces;
- advertising or audience activation settings owned outside GTM.

Resolve the current configuration surface from official documentation. Classify each dependency as already confirmed, separately authorized, required external work, intentionally untouched, or blocking.

## Apply consent

Use strict/basic gating by default:

- create or reuse `Block - <CMP> - GA4 denied`;
- block unknown, uninitialized, and denied states;
- apply the gate to the config and all GA4 event tags in scope only after confirming that any shared Google tag destinations require a compatible basic route.

Use advanced Google Consent Mode only when explicitly requested and approved. In that route, follow the dedicated consent reference and do not attach a blocking trigger that suppresses the documented denied-state behavior.

If a Google tag also serves Google Ads, Floodlight, or another destination with a different consent route, follow the shared-execution-unit rule in the Google consent reference. Do not let a GA4 block silently disable an approved advanced destination or let that destination's advanced route expose GA4 contrary to its selected basic policy.

## Verify the saved analytics setup

Re-read the saved Google tag, event tags, variables, settings, normal and blocking triggers, folders,
and all references. Confirm the exact approved event, timing, filter, field set, source/literal, item
scope, DLV versions, `send_page_view`, consent route, firing option, connected destinations, and
idempotent rerun. Re-run approved-to-saved conformance before `Configured`.

Keep custom definitions, key-event designation, Enhanced Measurement, data-stream, Google tag
destination, and publication work separate from the GTM completion claim. Do not claim browser or
GA4 reporting behavior from saved configuration.

## Naming examples

| Object | Example |
| --- | --- |
| Google tag | `GA4 - Config` |
| GA4 event | `GA4 - Event - generate_lead` |
| GA4 ecommerce event | `GA4 - Event - purchase` |
| Source DLV | `DLV - page_location` |
| Measurement ID | `CST - GA4 measurement_id` |
| Custom Event trigger | `CE - generate_lead` |
| Consent exception | `Block - Didomi - GA4 denied` |
