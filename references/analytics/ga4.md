# Analytics tags

Use [intake and conformance](intake-and-conformance.md) for exact approved analytics semantics.
This route coordinates Google/GA4 feature owners.

## Read by changed feature

- For every GA4 event: [ga4 validity](ga4-validity.md).
- For field placement/inheritance: [google fields](google-fields.md).
- When changing Google configuration, connected destinations, page views, automatic collection,
  diagnostic fields or transport: [ga4 ownership](ga4-ownership.md).
- For ecommerce: [ga4 ecommerce](ga4-ecommerce.md).
- For user properties, User-ID or user-provided data: [identity](../data/identity.md).
- For CMP grants, blocks and timing: [web](../consent/web.md). Existing advanced behavior
  requires an applicable approved topology; resolve a policy conflict before adding a consumer.
- For naming and shared values: [organization](../organization.md).
- For multiple environments/destinations: [routing](../routing.md).


## Configure and verify the event

Resolve the exact official event classification and its approved event/item field contract through
[GA4 validity](ga4-validity.md). [Mapping](../data/mapping.md) establishes actual source keys and
terminal shape; [Google fields](google-fields.md) establishes native placement. Apply the changed
feature guides above and [linker guidance](../web/linker-cross-domain.md) when attribution/domain
behavior is affected.

Carry approved semantics through reviewed native intent, saved comparison and no-op convergence.
[Acceptance](../core/acceptance.md) separates saved proof from external administration and runtime QA.
