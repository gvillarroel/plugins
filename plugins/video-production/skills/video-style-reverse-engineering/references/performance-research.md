# Performance research

## Contents

- [Scope and discovery](#scope-and-discovery)
- [Comparable rankings](#comparable-rankings)
- [Evidence limits and selection](#evidence-limits-and-selection)

## Scope and discovery

Define the decision: audience attention, explanation, product demonstration or
another user goal. Public reach is evidence of distribution, not sales or
retention. Set platform, topic/audience, language, video format, duration range
and search period before selecting winners. If unspecified, state a task-based
assumption and begin. Honor fixed-source and offline constraints.

Search several angles: the user's topic plus editing terms, original creator
uploads, recent examples, and plausible controls. A practical first pass is
12–24 candidates across 3–6 emerging families, adjusted to the available evidence
and task. Search results are candidates, not the ranking. Avoid counting the
same upload, reupload or campaign repeatedly as independent support. Retain
normal or weaker videos from comparable channels to reduce winner-only bias.

Verify the actual video URL and creator. Record exact title, stable channel ID,
publication date, duration, explicit platform format, public views and available
likes/comments, retrieval time in UTC, metric definition and source. Record
missing fields as null. Do not infer Shorts from duration alone or mistake an
ad's destination link, tutorial or compilation for the original production.
Pinterest boards can supply visual inspiration without comparable outcome data.

Use public primary metadata or a connected authorized analytics source. For a
small public YouTube sample, metadata-only extraction avoids downloading every
clip:

```sh
uvx --from yt-dlp yt-dlp --flat-playlist --dump-single-json "ytsearch12:<topic and editing style>"
uvx --from yt-dlp yt-dlp --skip-download --write-info-json --no-playlist --paths research/metadata <selected-video-url>
```

Verify fields from each actual video; flat search metadata can be incomplete.
Keep the dated snapshot separate from the reusable instructions. Record query,
selection/exclusion reasons and failed access. Refresh stale research when the
user requests current winners or a new market; never present an old library as
a fresh search.

## Comparable rankings

Keep separate lists for public reach, average views per elapsed day, and
channel-relative standout performance. Do not hide them in one weighted score.
Compare only compatible platform, native format, metric definition and duration
band. Keep new releases and historical examples in their own partitions. An
unverified format or metric definition cannot establish a comparable winner.

For the deterministic helper, write a JSON object containing `observed_at`
(UTC ISO timestamp), `candidates`, and optional `baselines`. Each row has:

```json
{
  "id": "video-id",
  "url": "https://www.youtube.com/watch?v=video-id",
  "title": "Original title",
  "creator": "stable-channel-id",
  "platform": "youtube",
  "format": "standard",
  "metric_definition": "public-standard-views",
  "published_at": "2026-10-01T12:00:00Z",
  "duration_seconds": 90,
  "views": 12000,
  "likes": null,
  "comments": null,
  "style_id": "kinetic-type"
}
```

The numbers above are illustrative, not research evidence. Keep display names,
source receipts, format-verification notes and visual findings in the research
record alongside the helper input. Use `shorts` only after verifying that native
format; label unavailable evidence rather than forcing an eligible category.

```sh
uv run --script <skill-dir>/scripts/rank_references.py research.json --output ranked.json
```

The helper separates fresh videos under seven days, mature videos up to 730
days and older examples. It computes cumulative views divided by elapsed days;
this is a lifetime average, not recent growth velocity. Actual growth requires
two dated snapshots of the same metric.

Use its four fixed duration bands: under 60 seconds, 60 to under 180, 180 to
under 600, and 600 seconds or more. Preserve the emitted JSON and ranking method
when writing the report. Do not substitute different bins or a hand-written
ranking implementation. If the user requests a different comparison, report it
as a separate explicitly defined analysis rather than overwriting this result.

Channel-relative ratio = candidate mean views/day divided by the median mean
views/day of at least five distinct comparable peer uploads. Peers must have
the same stable creator, platform, format, metric definition and duration band,
publication dates within 180 days and elapsed ages within a factor of two.
Selected candidate IDs are excluded from the baseline pool. All occurrences of
a duplicated baseline ID or source video are excluded, rather than keeping the
first duplicate as an additional peer. Record actual peer
IDs, sample size and median; do not fabricate a channel-wide baseline from
subscriber count or a few handpicked successes. This ratio remains a discovery
heuristic, not an unbiased causal estimate; peer selection and topic matter.

When valid peers are unavailable, retain the raw/public reach observation and
explicitly mark channel-relative standing unknown. A missing ratio is not zero.
Likes/views and comments/views are optional response indicators, not retention
or complete engagement rates; missing shares, saves and impressions remain
unknown. Avoid rankings driven by tiny denominators or hidden counts.

## Evidence limits and selection

Check brand size, topical demand, launch timing, paid promotion, collaborations,
thumbnail/title appeal, language and reuploads as competing explanations.
Unknown advertising spend is unknown, not proof of organic performance. Select
strong within-channel examples when supported, then choose a style that fits
the user's content and production constraints. Without a common performance
cohort, order style recommendations by explicit evidence tier and task fit;
do not rank style families by pooled lifetime views.

YouTube changed public Shorts views on 2025-03-31 to include starts/replays;
owner Analytics retains a distinct engaged-views metric. The current Data API
documentation also describes a 2026-08-24 change to `viewCount` for all formats,
counting at play start. Verify the definition for the actual collector and
snapshot date: do not silently equate a watch-page counter, API field, historical
snapshot and owner engaged-views report. Keep native formats separate even
when a counter's definition is shared. Public statistics do not expose a
competitor's retention or thumbnail CTR. Use authorized owner reports when
those outcomes are required.
Primary documentation: [video statistics](https://developers.google.com/youtube/v3/docs/videos#statistics),
[Shorts view definitions](https://support.google.com/youtube/answer/10059070?hl=en),
and [authorized channel reports](https://developers.google.com/youtube/analytics/channel_reports).
