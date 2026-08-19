# Server LinkedIn Conversions API

## Route

Use LinkedIn Conversions API current official schema and an inspected compatible GTM server
template. Record conversion rule/account identity, event time, source, user identifiers/hashing,
click identity, consent, authentication, and request diagnostics. Do not infer the server event from
the Insight Tag label alone.

For browser/server overlap, verify current LinkedIn dedup requirements and one occurrence-level
`eventId` across the relevant rule/routes. Keep external conversion-rule and token administration
outside GTM.

Official sources:

- https://learn.microsoft.com/en-us/linkedin/marketing/integrations/ads-reporting/conversions-api
- https://learn.microsoft.com/en-us/linkedin/marketing/conversions/deduplication

Fail closed if the rule, token, template provenance/hosts, matching fields, consent, or dedup route
is not proved.
