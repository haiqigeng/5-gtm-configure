# Quotas and run sizing

## Quotas and run sizing

Google's [GTM API quota](https://developers.google.com/tag-platform/tag-manager/api/v2/limits-quotas)
(checked 2026-09-30) is 10,000 requests/project/day and 25 requests per sliding 100 seconds.
Quota exhaustion returns HTTP 403 with a quota-specific message; an arbitrary 403 is not a
retryable quota error. Connectors can impose their own limits, including 429 responses.

The packaged adapter recognizes structured `error.code: 403` only when every entry in
`error.errors` carries `rateLimitExceeded` or `userRateLimitExceeded` (the documented
[Google structured rate-limit reasons](https://developers.google.com/workspace/calendar/api/guides/errors)).
It never infers a retry from prose, a generic forbidden response, daily quota exhaustion, or an
unknown dispatched write. The GTM quota page establishes the status and window; it does not
specify the JSON reason vocabulary. Preserve that structured endpoint rejection in the connector.
The existing pagination and operation retry loops allow two retries, with a 100-second wait for
these typed GTM quota refusals and a 100-second default maximum wait. A configured lower maximum
stops safely instead of retrying early. Exhausted post-write readback retains uncertainty and
never repeats the accepted write. Startup identity/registration checks and final convergence
reads can still stop on quota; retain their evidence and resume through the documented workflow.

This is bounded recovery, not proactive project-wide pacing. Before a large run, inspect the
connector's actual request pacing/retry behavior and record it with the selected connection.
The connector must account for API requests behind each MCP call and other callers sharing the
project; this package cannot infer that aggregate traffic. The relay's 1800-second run budget
includes local quota waits (up to 200 seconds per exhausted retry loop); its 180-second per-call
budget covers each dispatched MCP call, not the local wait between calls. Budget additional waits
explicitly and preserve the uncertain-write journal if the overall deadline interrupts work.


Estimate planned reads, paginated relists, writes, readbacks and final convergence before a large
run. MCP calls need not map one-to-one to API requests. Use observed connector latency and quota
behavior, local computation and a recovery margin to set `runTimeoutSeconds`; the 1800-second
default is not a plan-size guarantee. Do not add quota delay and CPU as a proven minimum because
they may overlap. If the workload exceeds the measured budget, use independently complete approved
event groups, maintaining shared dependencies and the journal. Ten events is not a universal safe
limit. Never extend a deadline as permission to replay an uncertain write.

Repeated redaction scans are cached by a digest of the entire input and all scan context, including
public declarations and secret paths. The bounded cache holds detector metadata, not raw literals.
Fresh per-create absence checks remain mandatory; performance optimization does not relax them.
