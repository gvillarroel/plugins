# Two local API approaches

Use this recipe when comparing a direct REST handler with a Google SDK handler
while retaining a Google user identity. Keep the same operation, scope,
pagination budgets and report contract so the comparison measures the routes
rather than different tasks.

## Shared bounded audit pattern

For a useful read-only PoC, list object metadata in a known bucket/prefix,
follow continuation tokens, count objects, sum integer sizes and group names
by their final lowercase suffix. Treat a dotfile or a name without a suffix as
`(none)`. Fetch only `items(name,size),nextPageToken`; no content, ACL, project
discovery, upload or infrastructure creation is needed.

Accept explicit bucket, literal prefix, expected account, page size, page cap
and object cap. Reduce the final request size to the remaining object budget.
Never turn a capped scan into a complete-bucket total. Test normal completion,
empty pages, repeated continuation tokens, exact caps and more data at a cap.

Return identity, scope, object count, total bytes, extension counts, pages,
limits, completion/truncation state and separate auth/API/total timings. Keep
resource names and credentials out of the report when aggregates suffice.

## REST with existing gcloud authorization

Use a standard-library HTTP client with the fixed Storage JSON API endpoint.
Apply the existing environment and saved-property identity checks, then verify
the explicit stored user and capture a token internally. A safe gcloud
configuration projection can return JSON `null` when every selected property
is unset; treat only that root null as an empty projection, while rejecting
other unexpected shapes. Refuse redirects and sanitize HTTP/auth errors.

This route adds no Python packages. It depends on the installed gcloud CLI at
runtime, and subprocess startup/checks can dominate a short audit. Maintain
HTTP parameters, continuation handling and token reacquisition explicitly.

## SDK with explicit user ADC

Use a pinned Google Cloud Storage client and an explicit authorized-user ADC
file. Reject service accounts, impersonation, alternate token domains and
metadata-server/default-identity fallback. Verify the actual token's email
against the expected user; do not trust only an optional account label in the
file. A fixed Google userinfo endpoint requires the corresponding email scope.
Keep token refresh and Storage paging in the client library, with explicit
budgets, trusted endpoints and bounded timeouts.

When a valid Google CLI authorization already exists, the documented command
`gcloud auth login USER_EMAIL --no-activate --update-adc` can reuse it and write
ADC. A second browser flow is not inherently necessary. Run in the user's
approved configuration location; this command overwrites ADC at that location.
Use `gcloud auth application-default login` when a separate SDK authorization
is needed. These are explicit setup choices, not actions for every audit.

The SDK can run without gcloud after setup. ADC is a separate credential
configuration and does not follow later changes to gcloud's active account.
Require the expected account on each audit and never overwrite the credential
input with an output report.

## Compare and validate

1. Use synthetic pages with independently calculated aggregates; compare
   identity, scope, limits, counts, bytes and completion, excluding timings.
2. Exercise credential-type/account mismatch, override rejection, malformed
   input, missing ADC, HTTP failure and secret-free errors.
3. Run both on the same authorized live bucket and literal prefix, then test
   one cap and an empty prefix without uploading fixtures.
4. For native Claude commands, use a thin argv-based adapter and return the
   helper's sanitized report. Verify actual command receipts and model usage
   separately from synthetic engine tests and interactive painting.
5. Separate dependency installation/cold startup from helper auth/API timings.
   Do not infer a stable performance ranking from one observation.

Both routes need the requested method's IAM access, scopes and any documented
quota-project requirement; neither inherently needs a server or service
account. Prefer REST for a small API-specific extension with an existing CLI
session. Prefer a supported SDK for repeated workflows where library-managed
credentials, types, paging and maintenance offset dependency/setup costs.
An API method can predate its SDK wrapper; check the exact method before
choosing the library route.

Primary sources: [REST authentication](https://docs.cloud.google.com/docs/authentication/rest),
[gcloud login and ADC update](https://docs.cloud.google.com/sdk/gcloud/reference/auth/login),
[user ADC](https://docs.cloud.google.com/docs/authentication/set-up-adc-local-dev-environment),
[Storage list_blobs](https://docs.cloud.google.com/python/docs/reference/storage/latest/google.cloud.storage.client.Client#google_cloud_storage_client_Client_list_blobs).
