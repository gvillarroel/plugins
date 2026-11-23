# Reference acquisition

Use the researched shortlist or user-provided local files. For a URL, identify the service and the
specific clip before downloading. Record source URL, creator, retrieval date,
local path and intended use. A board may contain several unrelated styles;
download only the selected references unless the user requests the collection.

For supported galleries and Pinterest collections, consult the current
[gallery-dl supported-site table](https://github.com/mikf/gallery-dl/blob/master/docs/supportedsites.md).
For YouTube and supported video hosts, use
[yt-dlp](https://github.com/yt-dlp/yt-dlp). Scope downloads to the task folder:

```sh
uvx --from gallery-dl gallery-dl --dest refs <selected-url>
uvx --from yt-dlp yt-dlp --no-playlist --write-info-json --paths refs --output "%(id)s.%(ext)s" <video-url>
```

Check the exit code and actual files. Collections can contain images rather
than playable clips. Probe the downloaded video before claiming success.
Do not promise every host works: support, authentication and rate limits vary.
If an initial attempt fails, inspect the error and use a supported alternative
within the same scope. Stop repeated rate-limited attempts. Request a local copy
only when accessible references are necessary and no usable copy is available.

For a narrated tutorial, captions can recover the method without revealing the
editing style. Select one available language rather than requesting every
auto-translated track:

```sh
uvx --from yt-dlp yt-dlp --skip-download --write-auto-subs --sub-langs es --sub-format json3 --paths refs <video-url>
```

Treat auto-captions as fallible: verify tool names against the description or
official documentation. Preserve only short needed quotations; keep a compact
method summary instead of redistributing the full transcript.

For reusable asset libraries, distinguish reference-only clips from permitted
production assets. Store the asset's source, creator, license or permission and
local path. Reuse cached assets for a batch when permitted. Keep API credentials
in the provider's normal secret store; never embed them in the style recipe,
HTML, generated skill or logs. Use only connected providers with the required
capability; otherwise accept user-provided assets or local graphics.
