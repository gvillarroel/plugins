# User authorization and minimum permissions

Reviewed against primary documentation on 2026-10-25.

## Contents

[Local command](#local-command-pattern),
[credential checks](#effective-credential-checks), [scope](#scope-and-errors),
[direct REST](#direct-api-methods-absent-from-gcloud),
[Claude recipe](#claude-specific-recipe), [sources](#primary-sources).

## Local command pattern

Use the installed Google Cloud CLI to reuse the user's approved credential
store. It owns browser OAuth, token storage and renewal. Do not read credential
databases or print access/refresh tokens. No server, custom OAuth client,
service account, ADC login, or deployed infrastructure is required.

```text
gcloud auth list --format=json(account,status)
gcloud auth login USER_EMAIL --no-activate
gcloud storage buckets list --account=USER_EMAIL --project=PROJECT_ID --limit=100 --format=json
gcloud storage objects list gs://BUCKET/** --account=USER_EMAIL --limit=100 --format=json
```

Quote the format projection according to the executing shell. Pass argv arrays
when invoking a process API. Do not append raw command text or arbitrary
gcloud flags supplied by a user. Prefer narrow projections over full metadata
and object data; listing names does not require downloading object contents.

Use `gs://BUCKET/**` for nested object names or
`gs://BUCKET/reports/**` for a prefix. Quote the URI in a shell so gcloud, rather
than the shell, interprets the wildcard. The native command appends `**` to
the validated bucket/prefix argv value. An unadorned bucket listing can return
no direct objects while nested objects exist; do not infer an empty bucket
from that result. This was reproduced with a real bucket containing 84
nested objects during validation.

`auth login` reuses valid credentials. `--force` repeats the browser flow when
a fresh browser-authorization check is specifically requested; Google may
reuse a prior consent grant. `--no-activate`
preserves the selected active account; listing commands still need explicit
`--account`. The standard command has no documented `--scopes` switch.
Avoid `--update-adc` and `--enable-gdrive-access` for this task.

## Effective credential checks

Google documents this precedence: raw token environment variable, access-token
file, credential override file, active principal, then optional impersonation.
An explicit account flag does not override the higher-priority credentials.
Reject these settings, reporting names/presence only:

- `CLOUDSDK_AUTH_ACCESS_TOKEN`.
- `CLOUDSDK_AUTH_ACCESS_TOKEN_FILE`, or `auth/access_token_file`.
- `CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE`, or `auth/credential_file_override`.
- `CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT`, or
  `auth/impersonate_service_account`.
- `CLOUDSDK_AUTH_LOGIN_CONFIG_FILE`, or `auth/login_config_file`, when the
  minimal Google-account flow is expected; workforce federation requires its
  own deliberate workflow.

Use the current host API to inspect environment variable names without
disclosing values, or make child-process credential selection explicit and
verify the effective properties. Do not silently fall back to a service
account or metadata-server identity. Reject service-account identifiers in
this Google-user workflow. ADC's `GOOGLE_APPLICATION_CREDENTIALS` is a different
credential path: the gcloud commands here do not use ADC.

## Scope and errors

| Requested result | Minimum relevant permission | Boundary |
| --- | --- | --- |
| Objects in a known bucket/prefix | `storage.objects.list` on that bucket or applicable managed folder | No project discovery or project bucket listing required; folder-only grants may require a matching prefix. |
| Buckets in a named project | `storage.buckets.list` on that project | Does not enumerate direct access in other projects. |
| Discoverable projects | Resource Manager project visibility | Optional; cannot prove exhaustive Storage access. |

Use `storage objects list`, not a generic exact-object `storage ls`, when only
list permission is intended. Do not ask for ACL output, object decryption/hash
fetching, or object contents. Handle requester-pays billing as an explicit
additional requirement when encountered, not a hidden default.

A successful empty JSON array means no matching objects were returned. A 403
means access was denied; an auth error needs login; an unavailable project or
disabled API is another failure. Preserve those distinctions. At the row cap,
state that more entries may exist. A client limit bounds displayed results;
it is not a guarantee of a single API request or zero listing charges.

## Direct API methods absent from gcloud

An operation does not need a gcloud subcommand. For a documented Google Cloud
REST method that accepts user credentials, reuse gcloud for authentication and
make the HTTPS request in the local handler:

1. Apply the same effective-identity guards and explicitly select the user.
2. Capture `gcloud auth print-access-token --account=USER_EMAIL` internally.
   Keep its stdout out of transcript text, tool results, logs and saved files.
3. Send `Authorization: Bearer <token>` to the intended documented API host.
   Fix the supported method/host/path and validate resource arguments. Prevent
   authenticated redirects to other hosts; never forward this token to an
   arbitrary URL supplied by a user or returned by an API.
4. Process the documented JSON fields, pagination and long-running operation
   polling locally, with bounded requests/output and explicit mutation scope.
5. Return the useful result to Claude. Ask gcloud for another token when
   necessary instead of reading or maintaining refresh-token databases.

The method still needs the user's IAM permissions, applicable OAuth scopes,
an enabled target API, and any documented credential-type requirements.
Some APIs require an explicit `x-goog-user-project` quota project with
`serviceusage.services.use`. Do not add that requirement when the API works
without it, or interpret every quota-project error as requiring a service
account. Additional scopes require the corresponding authorization flow;
the standard Cloud login is not authorization for every Google service.

A client library with user ADC is an alternative for substantial SDK-based
code. It adds a separate credential configuration and identity-resolution
path. Prefer the existing gcloud-token route when minimizing prerequisites;
do not add ADC simply because the operation uses REST.

This is an authoring recipe, not an implemented generic `/gcs api` command.
A real bounded GET to the Storage JSON API returned one object and a next-page
indicator using an internally captured user token on 2026-10-25. That verifies
the authentication mechanism, not an unspecified API method, fresh consent,
or a new native-plugin operation.

## Claude-specific recipe

The native plugin registers `/gcs` through `$.command.register` in a
`session.start` hook and handles `command.run` without delegating to a model.
Its handler returns `{text}` to put the result in the conversation. Invoke
processes only through `$.process.run(argv, init)`; do not use an interpolated
shell command. Native Mods run with the local user's OS authority, so keep
the supported operations explicit and limited to listing plus user-invoked
login. Google OAuth/IAM and Claude's plugin trust are separate permissions.

The bundle targets Claude Code 2.1.299+ to omit a separate types declaration.
Load with `--plugin-dir` in a trusted workspace with Mods enabled. Global
installation, a marketplace, an MCP server, an API key, a Claude model turn,
and a webview are unnecessary for the deterministic transcript command.
The host may still impose account, managed-policy, or trust gates.

## Primary sources

- [Google Cloud CLI authentication and credential priority](https://docs.cloud.google.com/sdk/docs/authenticate).
- [gcloud auth login and browser options](https://docs.cloud.google.com/sdk/gcloud/reference/auth/login).
- [CLI authentication versus ADC](https://docs.cloud.google.com/docs/authentication/provide-credentials-adc).
- [Direct REST with Google user credentials](https://docs.cloud.google.com/docs/authentication/rest).
- [User access tokens and quota project requirements](https://docs.cloud.google.com/sdk/gcloud/reference/auth/print-access-token).
- [Storage CLI IAM permission matrix](https://docs.cloud.google.com/storage/docs/access-control/iam-gcloud).
- [Object listing reference](https://docs.cloud.google.com/sdk/gcloud/reference/storage/objects/list).
- [Project-scoped bucket listing](https://docs.cloud.google.com/storage/docs/json_api/v1/buckets/list).
- [Claude Mod creation and no-build loading](https://code.claude.com/docs/en/plugins/mods/create).
- [Claude commands and process API](https://code.claude.com/docs/en/plugins/mods/api).
- [Claude native plugin file contract](https://code.claude.com/docs/en/plugins/mods/reference).
