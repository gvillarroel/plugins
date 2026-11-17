---
name: gcs-user-access
description: List Google Cloud Storage buckets and objects with the signed-in user's Google permissions, and provide a local Claude Code /gcs command without a server, service account, custom OAuth application, or model turn. Use for end-user Storage browsing, Google authorization, and minimal Claude Code cloud plugins.
---

# Cloud Storage with the user's identity

Prefer the installed Google Cloud CLI and its existing user authorization.
Use the bundled native Claude Code plugin when the user wants a command in
that interface. A plain CLI listing needs no plugin. Resolve ambiguous
"Cloud Code" wording before claiming Claude-specific support.

## Choose the smallest useful operation

1. Accept a known `gs://bucket` or bucket prefix when available. Object listing
   requires `storage.objects.list`; a grant limited to a managed folder may
   require listing its matching prefix. Discovering projects or listing their
   buckets is unnecessary for that path.
2. For a project's buckets, require its project ID and
   `storage.buckets.list`. Project discovery is optional and incomplete.
3. Bound listings to 100 entries. Label empty lists, permission failures,
   authentication failures, and truncated results separately. Do not claim
   that a project scan discovers every resource the user can access.

## Use Claude Code

The runtime template is [assets/plugin](assets/plugin/). Copy its contents to
a new user-selected plugin directory, or load the bundled directory directly:

```text
claude --plugin-dir <absolute-path-to-assets/plugin>
```

The template has three files: [manifest](assets/plugin/.claude-plugin/plugin.json),
[module loader](assets/plugin/hooks/hooks.json), and
[native command implementation](assets/plugin/hooks/register.js). Inspect the
implementation for its exact command syntax when preparing usage instructions.

Use a trusted workspace with Mods enabled and Claude Code 2.1.299 or newer.
The bundled command uses no model completion, Node runtime, build, network
service, API key, or marketplace. The installed `gcloud` CLI must be available
to the process. On Windows, follow the template's launcher guidance if PATH
resolution fails; do not construct a shell command from user arguments.

The `/gcs` command provides help, identity status, optional project discovery,
project bucket listing, known-bucket object listing, and explicit user login.
Run `/gcs help` for its exact arguments. It returns text in the Claude Code
transcript. Do not describe a terminal result as a Desktop pane or MCP App.

Validate a copied plugin with `claude plugin validate <plugin-dir> --strict`.
A headless command can exercise the native path with
`claude -p "/gcs status" --plugin-dir <plugin-dir>`; distinguish a loader
test from a real Google call and actual visible UI. Respect host sign-in or
workspace-trust gates when encountered.

## Authorize the Google account

Reuse valid credentials when available. Run the plugin's explicit login
action, or `gcloud auth login USER_EMAIL --no-activate`, when authorization
is missing. Let the human complete Google sign-in and any consent presented.
A forced browser-authorization test is a distinct operation; an existing
consent grant may still be reused. Do not label credential reuse as fresh
browser authorization or newly granted consent. Store credentials only in the user's approved
CLI configuration location, never in versioned source or logs.

The plugin must reject credential overrides and service-account impersonation
before claiming an end-user identity. An active-account label alone does not
prove which credential authenticates the request. For direct CLI work, inspect
the override names and configuration properties listed in
[authentication-and-permissions.md](references/authentication-and-permissions.md)
without printing secrets. Select the account explicitly for each request.

Do not add `gcloud auth application-default login`, service-account keys, IAM
grants, API enablement, or cloud resource creation to this listing workflow.
Google IAM enforces the user's resource access. The standard CLI login has
broader OAuth scopes than Storage listing alone; it is the low-infrastructure
option, not a custom Storage-only OAuth client.

For a requested Storage method absent from gcloud, read
[the direct REST recipe](references/authentication-and-permissions.md#direct-api-methods-absent-from-gcloud).
Keep gcloud as the user credential provider and implement the operation with
HTTP. The current native template exposes its listed operations only; a new
API method needs its own handler rather than an unrestricted URL proxy.

For two comparable local API proofs, use the
[REST-versus-SDK recipe](references/rest-versus-sdk.md). Compare the same
bounded operation and user identity; reuse existing authorization for ADC
setup when possible rather than assuming another browser flow is required.

## Verify and report

Check the identity, list the requested scope, and preserve the actual failure
if it is denied. Use synthetic tests for nonempty object formatting when the
user's bucket is empty; never upload a fixture to obtain a successful result.
Record credential reuse, human consent, real API calls, native-engine tests,
and visible UI observations as separate evidence. Read the compact reference
for direct commands, permission boundaries, and primary sources.
