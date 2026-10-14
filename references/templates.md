# Template governance

## Select a supported implementation

Choose the first compatible route that satisfies the current official product contract:

1. GTM native/built-in template;
2. official vendor-published template;
3. reviewed Community Template Gallery template;
4. approved organization-owned template;
5. officially documented Custom HTML/Image when the supported-template routes cannot represent the requirement.

Compatibility comes from the exact installed fields, permissions and behavior. Establish publisher
and repository identity independently of Gallery membership. A missing compatible template takes
its installation/update path under [target authority](core/authority.md#target-authority).
Availability, runtime values and adapter convenience are distinct from implementation compatibility.

## Inspect the lifecycle action

Record template identity, publisher/repository, installed version/commit, documentation, fields,
defaults, required inputs, automatic behavior, consent APIs, matching/events, existing consumers,
and permissions covering domains, globals, cookies, storage and data access. Inspect applicable
container/zone restrictions and linked-container ownership.

| Action | Required evidence and authority |
| --- | --- |
| Inspect/use | Installed compatible implementation and its consumers within the authorized configuration. |
| Import | Installation authority, publisher/repository and permission review. |
| Update/replace | Update authority, consumer inventory, field/permission diff and saved rollback evidence. |
| Author/change code | Custom-template development authority and security review. |

Each template mutation records its exact added/removed permissions and inspected version/repository
locator in the run. Preflight surfaces expanded execution or data access for the authorized action.
This evidence establishes the inspected surface; publisher reputation and unavailable code remain
separate uncertainties. Missing authority, adapter capability or required evidence holds the affected
implementation through [dependency readiness](core/execution.md#contain-failures-by-dependency).

## Map the product contract to installed fields

Keep the destination parameter and template UI field distinct. Every required parameter has an
authoritative mapping into the installed schema. Resolve discrepancies through the template version,
repository/release notes, accessible field code and permissions, and compatible native/newer routes.

Consent implementations use verified CMP/templates and their GTM consent APIs. For an officially
supported HTML/Image route, record the exact source, timing, consent and denied-state behavior,
CSP impact, failure behavior and why the template routes cannot represent the requirement.
Container security controls and Zone restrictions retain their own explicit authority; an unresolved
restriction becomes the affected implementation's dependency.

## Verify the saved implementation

Use [execution](core/execution.md) for readback and no-op proof. Compare the inspected identity/version,
stored field types/shapes, approved permissions, selected automatic events/matching, and intended
consent/trigger references. Include template evidence even when the template itself is reused.

## Preserve inspected source evidence

An exact-source `public_identifiers` declaration with `classification: inspected-template-source`,
`path: ["templateData"]`, complete `value_sha256`, official `source_url` and inspection reason binds
classification to the complete inspected source. Its recognized non-operational content comprises
email examples in the unique `___TESTS___` section and a static non-private fourth `injectScript`
argument ([script cache identifier](https://developers.google.com/tag-platform/tag-manager/templates/api#injectscript))
with its symbol copies in test mocks. The validator continues credential, private-key, executable
personal-data, permission and unrelated-path inspection. Full source bytes remain available for
comparison under [privacy and evidence rules](core/execution.md#handle-secrets-without-false-equality).

## Govern server templates

Inspect server-specific network hosts, secret fields, automatic Event Data mapping, hashing,
batching, response and deduplication behavior through the same lifecycle. Establish official API
support and installed GTM compatibility separately. Server implementations use native or compatible
server templates. A generic HTTP Request/custom server implementation requires the exact official
destination contract, credential owner, network permission, response/retry behavior, consent and
deduplication model, with a documented compatibility gap in the preferred routes.

## Official entry points

- https://support.google.com/tagmanager/answer/9454109
- https://developers.google.com/tag-platform/tag-manager/templates
- https://developers.google.com/tag-platform/tag-manager/templates/permissions
- https://support.google.com/tagmanager/answer/7647043
