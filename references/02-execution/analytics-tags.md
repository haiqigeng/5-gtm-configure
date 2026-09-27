# Analytics tags

Implement the approved analytics event names, exact outgoing fields, source mappings, literals and
timing. Current official documentation establishes technical validity; a valid alternative is an
advisory, not permission to redesign the plan. See
[tracking-plan-fidelity-and-conformance.md](tracking-plan-fidelity-and-conformance.md).

## Read by changed feature

- For every GA4 event: the safety gate and event procedure below, plus
  [ga4-collection-safety.md](ga4-collection-safety.md).
- For field placement/inheritance: [google-field-ownership.md](google-field-ownership.md).
- When changing Google configuration, connected destinations, page views, automatic collection,
  diagnostic fields or transport: [ga4-configuration-and-lifecycle.md](ga4-configuration-and-lifecycle.md).
- For ecommerce: [ga4-ecommerce.md](ga4-ecommerce.md).
- For user properties, User-ID or user-provided data: [first-party-data.md](first-party-data.md).
- For CMP grants, blocks and timing: [cmp-consent.md](cmp-consent.md). Existing advanced behavior
  requires an applicable approved topology; resolve a policy conflict before adding a consumer.
- For naming and shared values: [naming-and-reuse.md](naming-and-reuse.md).
- For multiple environments/destinations: [multi-destination-routing.md](multi-destination-routing.md).

## Apply the GA4 safety gate

Load `ga4-collection-safety.md` for every Google tag or GA4 event. Before mutation, validate current
official names, reserved prefixes, required fields, types, limits, final outgoing parameter/user-
property counts, item scope, and PII risk. Count inherited Event Settings fields as part of each
event's outgoing payload.

Classify a valid recommendation difference as advisory and preserve the approved contract. Stop an
invalid or unsafe requirement. Never silently truncate a value, coerce a type, delete a parameter,
or add a field to remain within a limit.

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

## Verify the saved analytics setup

Re-read the saved Google tag, event tags, variables, settings, normal and blocking triggers, folders,
and all references. Confirm the exact approved event, timing, filter, field set, source/literal, item
scope, DLV versions, `send_page_view`, consent route, firing option, connected destinations, and
idempotent rerun. Re-run approved-to-saved conformance before `Configured`.

Keep custom definitions, key-event designation, Enhanced Measurement, data-stream, Google tag
destination, and publication work separate from the GTM completion claim. Do not claim browser or
GA4 reporting behavior from saved configuration.
