# Native trigger and variable selection

Author `customEventFilter`, `filter`, and `autoEventFilter` as native Condition arrays with typed
Parameter rows. A compact event-name string is not a native custom-event filter. For an exact
custom event, use an `equals` condition with `arg0: {{_event}}` and `arg1` holding the approved
event name, both native TEMPLATE parameters; use the inspected native regex condition when needed.

## Contents

- Cover every applicable web trigger
- Cover built-in and user-defined variables
- Use lookup tables selectively
- Account for environments and hostnames

## Cover every applicable web trigger

Use the current GTM UI/API to identify the complete web trigger surface. Apply these stable decision
families:

| Trigger family | Required judgement |
| --- | --- |
| Consent Initialization / Initialization | Use only for documented consent/default or earliest initialization work; do not send business events here. |
| Page View / DOM Ready / Window Loaded | Choose the earliest event that has every required value and DOM dependency; prevent automatic/manual overlap. |
| Custom Event | Preferred for approved application success events and vendor-neutral dataLayer timing. |
| Just Links | Use only for a real anchor-navigation interaction. Configure `Wait for Tags` and `Check Validation` only after proving their page-enable condition, timeout, browser behavior, and navigation impact; those options are mechanics, not conversion-success proof. |
| All Elements | Use when the approved interaction is not reliably represented by an anchor. Filter on the clicked element/ancestor contract deliberately. This trigger does not offer `Wait for Tags` or `Check Validation`; those options belong to Just Links and Form Submission. |
| Form Submission | Use only when the browser submit event honestly represents the approved outcome. Configure waiting/check validation and the enable condition from current proof; a valid browser submit is not proof of backend success. |
| Element Visibility | Define selector/element source, minimum percent, minimum on-screen duration, DOM-change observation, once-per-page/element behavior, and page scope. Dynamic observation cost and repeated elements must be intentional. |
| Scroll Depth | Define vertical/horizontal direction, percentage/pixel thresholds, page scope, and whether each threshold firing is a distinct approved interaction. Reconcile GA4 Enhanced Measurement scroll. |
| YouTube Video | Enable the exact built-ins and capture options required for start/progress/complete; define percentage thresholds and JavaScript API support. Reconcile embedded-player availability and any automatic video measurement. |
| History Change | Use for an approved SPA fallback; define which history sources/states qualify, retain old/new URL values correctly, and reconcile application and Enhanced Measurement routes. |
| Timer / JavaScript Error / other web trigger | Use only when the tracking plan explicitly measures that interaction and current built-ins expose the required source. Define limit, interval, error fields, and page scope as applicable. |
| Trigger Group | Treat it as an AND lifecycle: it fires after every member has fired since the group became active, with member repetition and page lifecycle verified. Do not use it to simulate consent revocation or a mutually exclusive predicate. |

For every trigger, record event type, all-versus-some selection, row-level AND filters, regex intent,
repeatability, required built-ins, and positive/negative static examples.
Verify field applicability in the [current Trigger API](https://developers.google.com/tag-platform/tag-manager/api/reference/rest/v2/accounts.containers.workspaces.triggers).

## Cover built-in and user-defined variables

Enable only the built-in variables required by an approved mapping or trigger and record each
consumer. Inspect page, click, form, history, video, scroll, visibility, error, and utility built-ins
from the current web-container surface; do not enable an entire family speculatively.

For user-defined variables, choose from the current native surface by semantics:

- Data Layer, constant, URL, referrer, first-party cookie, JavaScript variable, DOM element, auto-
  event, lookup table, regex table, random/undefined utility, and Google settings variables where
  applicable;
- narrow Custom JavaScript only when native variables cannot express the required pure output;
- installed variable templates only after the same publisher/version/permission gate as tag
  templates.

Record return type, event/state lifetime, missing behavior, dependencies, and every consumer. Avoid
DOM, cookie, global-JavaScript, random, or auto-event sources when an approved dataLayer value exists.

## Use lookup tables selectively

Create a lookup or regex table only when:

- at least two real input scenarios need a mapping;
- the mapping is deterministic and easier to understand than repeated conditions or code;
- every input/output and default/no-match behavior is defined;
- the table reduces real duplication;
- representative inputs can be tested.

Apply this judgement to analytics and media alike. Do not force a table into a direct one-to-one mapping.

## Account for environments and hostnames

Reuse or create environment/hostname mappings only when the implementation genuinely differs by environment or region. Prefer one tested LUT/RLT over duplicated tags when the destinations and consent policy remain semantically aligned.

Never send staging/test traffic to a production destination unless explicitly intended. Do not infer an environment mapping from hostname alone without confirming the target architecture.
