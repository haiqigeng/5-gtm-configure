# Template governance

## Contents

- [Choose the safest supported implementation](#choose-the-safest-supported-implementation)
- [Inspect before adding or updating](#inspect-before-adding-or-updating)
- [Map documentation to the installed fields](#map-documentation-to-the-installed-fields)
- [Avoid Custom HTML for consent and supported products](#avoid-custom-html-for-consent-and-supported-products)
- [Verify after mutation](#verify-after-mutation)
- [Official entry points](#official-entry-points)
- [Govern server templates](#govern-server-templates)

## Choose the safest supported implementation

Use this preference order when it satisfies current official vendor requirements:

1. GTM native/built-in tag template;
2. current official vendor-published template;
3. reviewed Community Template Gallery template;
4. approved organization-owned custom template;
5. Custom HTML or Custom Image only when no suitable template exists and the vendor officially documents that route.

Do not assume that a Community Template Gallery entry is endorsed by Google. Verify publisher and repository independently.

This order is enforceable. Inspect the native and installed template surface before creating the
tag. If a compatible template exists, use it. Do not choose Custom HTML because it is familiar,
because the adapter exposes it more easily, or because a runtime value might be empty.

## Inspect before adding or updating

Record:

- template name, type, publisher, repository, and documentation;
- installed version/commit or available version evidence;
- requested permissions and allowed domains/global variables/cookies/storage;
- field names, defaults, required fields, and hidden automatic behavior;
- consent APIs/checks and automatic matching/event behavior;
- existing tags that consume the template;
- container/zone type restrictions, boundaries, and linked-container ownership when Zones are present;
- update diff and changed permissions when an update is available.

For every template create, update, or replacement, record a machine-readable permission delta in
the configuration-run artifact: exact added permissions, removed permissions, and inspected
version/repository locator. Surface new domains, script injection, network/API, storage, cookie,
global-variable, or data-access permissions in the preflight view. This is an evidence summary, not
a publisher reputation score or a claim that the template is safe.

Do not add or update a template as an incidental side effect. Obtain approval when installation, update, or new permissions materially expand execution or data access.

Treat template lifecycle actions separately:

- `inspect/use`: routine when an already installed compatible template supports the requirement;
- `import`: explicit installation authority plus publisher/repository and permission review;
- `update`: explicit update authority, consumer inventory, field/permission diff, and saved rollback
  evidence;
- `author/change code`: explicit custom-template development authority and security review; do not
  infer this from an ordinary tag-configuration request.

When an installation or update is required but not authorized or not supported by the active
adapter, mark the affected tag family `Blocked` and identify the exact template action needed.
Custom HTML is not a permission bypass.

When an adapter cannot read template code or permissions authoritatively, do not claim that a
custom/community template is safe merely because tags already use it.

## Map documentation to the installed fields

Keep the official destination parameter separate from the template UI label. Confirm that the installed template actually supports every required field and current schema.

If official vendor documentation and the installed template disagree:

1. check the template version and official repository/release notes;
2. inspect field code/permissions when accessible;
3. check whether a native/newer template supersedes it;
4. block the affected implementation if no authoritative mapping exists.

Do not force an official parameter into an unrelated custom-field slot.

## Avoid Custom HTML for consent and supported products

Do not use Custom HTML to set GTM consent state when a verified CMP/consent template can use the GTM consent APIs. Do not reimplement Google Analytics, Google Ads, Floodlight, or another natively supported tag in Custom HTML without a documented requirement and approval.

Apply the same rule to Meta, Microsoft Advertising, and every other product for which a compatible
native, vendor, reviewed Gallery, or approved organization-owned template is installed or can be
authorized. A product need not have a Google-native template for the supported-template rule to
apply.

When Custom HTML/Image is unavoidable, document script/pixel source, execution timing, selected consent mechanism and denied-state behavior, CSP impact, failure behavior, and the reason no supported template fits.

Do not modify Zones, linked containers, allow/block restrictions, or container security policy as an incidental configuration step. Record a restriction that prevents the requested tag as an external dependency or blocker unless that exact control is separately authorized.

## Verify after mutation

Re-read the saved tag and template. Confirm:

- template identity/version did not change unexpectedly;
- every field is stored in the intended type/shape;
- permissions remain within the approved scope;
- automatic events or matching features remain disabled unless explicitly selected;
- consent settings and triggers reference the intended objects.

Record the template in the configuration result even when no template change occurred.

## Official entry points

- https://support.google.com/tagmanager/answer/9454109
- https://developers.google.com/tag-platform/tag-manager/templates
- https://developers.google.com/tag-platform/tag-manager/templates/permissions
- https://support.google.com/tagmanager/answer/7647043

## Govern server templates

For each server template, inspect publisher, exact version, field schema, defaults, permissions,
allowed network hosts, secret fields, automatic Event Data mapping, hashing, batching, response,
and dedup behavior. An official vendor API does not make a community template official or
compatible. Import, upgrade, code edit, host/permission expansion, or custom server template
requires explicit high-impact authority.

There is no browser Custom HTML/Custom JavaScript escape hatch in a server container. A generic
HTTP Request or custom server template is last resort: require the exact official destination
contract, credential owner, network permission, response and retry behavior, consent, dedup, and no
supported safer route.
