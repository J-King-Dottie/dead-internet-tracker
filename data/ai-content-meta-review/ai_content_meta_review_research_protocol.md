# AI Content Meta Review Research Protocol

Use this when refreshing the published-estimates chart.

This is not a casual source hunt.
Treat it like a compact literature review plus a public-analysis sweep.

## Goal

Build a defensible chart of published estimates for the share of online content that is AI-generated or materially LLM-assisted.

The chart is allowed to mix narrower studies with broader ones.
But every row must make its scope obvious.
This is a pulse check on public analysis, not a peer-review-only bibliography.

## Search Standard

Do a broad sweep, not just a few obvious web searches.

Work year by year.
Treat each calendar year as its own research target.

For a full refresh from `2020` through `2026`:

- do a focused sweep for `2020`
- then repeat for `2021`
- and so on through `2026`

If a year-focused search surfaces a usable estimate for a different year, still record it.
But the queries themselves should stay tailored to the target year so the sweep does not collapse into the usual `2024-2026` pileup.

Minimum query volume:

- at least `25` distinct search iterations per target year
- do more when a year is producing good hits
- an iteration means one distinct search query, not one browser session
- grouped search calls are fine, but still count and vary the underlying queries

Each yearly sweep should deliberately mix:

- broad queries:
  - `AI-generated content percentage 2023`
  - `share of online content AI-generated 2021`
- corpus queries:
  - `news articles`
  - `web pages`
  - `blog posts`
  - `academic papers`
  - `peer reviews`
  - `profile images`
  - `videos`
  - `music uploads`
- platform queries:
  - Facebook
  - Instagram
  - X
  - Twitter
  - Reddit
  - LinkedIn
  - Medium
  - Quora
  - TikTok
  - YouTube
  - Wikipedia
- source-type queries:
  - report
  - study
  - survey with denominator
  - audit
  - benchmark
  - investigation
  - newsroom post
  - institutional summary
- backwards and forwards citation chasing from the strongest sources already in the table

Minimum search lanes:

- academic-first search:
  - arXiv
  - Google Scholar-style search
  - journal or conference pages when the paper is not on arXiv
- public-analysis search:
  - high-quality news coverage
  - industry research blogs
  - institutional writeups
  - analyst posts that cite real sources and methods
- platform-specific search:
  - Facebook
  - Instagram
  - X / Twitter
  - Reddit
  - Medium
  - Quora
  - LinkedIn
  - TikTok
- corpus-specific search:
  - web pages
  - news articles
  - academic literature
  - peer reviews
  - images
  - videos
  - profile images
  - public-knowledge platforms
- multilingual search when the English sweep looks thin
- citation chasing forward and backward from the strongest papers already in the table

For every target year, hit both:

- broad internet-level queries
- targeted platform and corpus queries

Do not stop after the broad internet-level queries fail.
That is exactly when the targeted platform and corpus lanes matter most.

## What Counts as Usable

Prefer estimates that actually measure content share.

Use source hierarchy, not source absolutism.

Best:

- page-, post-, article-, image-, or review-level prevalence estimates
- explicit percentages or cleanly recoverable counts
- clearly defined corpus and time window
- methods section that explains how AI attribution was done
- accessible primary source

Usable with caveats:

- strong platform-specific estimates
- event-bound estimates
- modality-specific estimates like images or profile pictures
- institution or industry studies with a real method and denominator
- reputable news coverage that cites a study, dataset, or methodology clearly enough to preserve the estimate honestly
- blog posts or analyst writeups that contain references, sample details, and enough method context to explain what was measured
- reputable secondary-source summaries when the original is unavailable but the summary is specific enough to preserve the estimate honestly
- company or platform newsroom posts when they report a measurable denominator and the figure is clear about what share of content is synthetic
- trade-press reporting when it carries a platform or industry estimate with enough methodological context to preserve the denominator honestly

Bias toward inclusion when a candidate is:

- genuinely a new estimate
- clear about corpus and denominator
- narrow but still honest and relevant
- not obviously duplicated elsewhere in stronger form

Do not require every row to be academic.
This chart is meant to capture the published pulse of public analysis, not just formal literature.

Do not include:

- AI recommendation or ranking-share metrics
- traffic metrics
- user adoption surveys
- “AI use” self-report surveys unless they measure content share
- policy announcements about labeling
- commentary pieces recycling someone else’s estimate without added sourcing or method detail
- vague claims like “AI is everywhere now”

## Source Hierarchy

When multiple sources carry the same estimate, keep the strongest one.

Preferred order:

- primary paper or report
- official dataset or appendix page
- institutional summary of the same work
- high-quality news article citing the work
- blog or analyst post citing the work

If the best available version is a news article or blog post, that is acceptable.
But only if it gives enough context to preserve:

- what corpus was measured
- what the denominator was
- when the estimate applies
- how the number was produced

## Deduping Rule

Do not treat the same estimate repeated through several channels as separate evidence.

Examples:

- if a blog post cites a paper and the paper is accessible, use the paper
- if a news article cites a report and the report is accessible, use the report
- if the underlying source is not accessible, keep the secondary source only once and mark it clearly as secondary

When in doubt, ask:

- is this a genuinely new estimate?
- or just another route to the same estimate?

Only new estimates belong in the table.

Important:

- same number
- same study
- same platform post
- same company release

should usually become one row, not several dots.

But a new yearly update from the same source family can be a new row if the estimate itself changed and the time window changed.

## What To Store For Every Candidate

Before deciding whether to include a source, capture these fields in notes:

- study name
- year of estimate
- publication date
  - store it as `YYYY-MM-DD`
  - inferred source dates are acceptable when that is all the source exposes, including source-URL or source-metadata dates
- source URL
- source type:
  - peer-reviewed
  - preprint
  - institutional report
  - industry study
  - news article
  - blog / analyst writeup
  - secondary summary
- platform or corpus
- modality:
  - text
  - image
  - video
  - mixed
- geography and language scope
- time window
- sample size
- unit of analysis
- numerator
- denominator
- exact estimate used
- whether the estimate is:
  - direct
  - detector-based
  - statistical / inferential
  - heuristic / marker-based
- whether it is:
  - broad
  - narrow
  - event-bound
  - political
  - platform-specific
- exact line, table, figure, quoted passage, or clearly attributable summary passage that supports the number
- reason included or reason rejected
- if secondary:
  - what underlying source it appears to rely on
  - whether that underlying source was found

## Notes Format

When a candidate becomes a kept chart row, rewrite `notes` as one paragraph with exactly three short sentences:

1. claim: what the source found, including the estimate and scope
2. method: how the source measured it
3. caveat: the main limitation

Do not keep a separate relevance sentence.
Do not leave the notes in abstract form.
The stored row should already be tooltip-ready.

## How To Convert Studies Into Chart Rows

The chart should not overweight one paper just because it has many slices.

Rules:

- one value per study per year
- if a study gives one broad overall number, use that
- if a study only gives several comparable sub-estimates for the same study-year, use the median unless there is a clearly more representative aggregate
- if a study gives a range, use the midpoint only if the range is explicitly reported and both ends are equally plausible
- keep the underlying sub-estimates in notes even if the chart only gets one study-year row
- if a secondary source reports a number but the underlying source is inaccessible, store that row with an explicit note that the number is coming through a secondary route

If a study publishes several same-year slices with equal sample sizes across categories, an equal-weighted aggregate can be more representative than a median.
Use that when the study design clearly supports it, and say so in notes.

## How To Treat Platform-Specific Studies

Platform rows are useful.
But store enough context that the tooltip can say exactly what they are.

Examples:

- Facebook long-form posts
- Instagram search results
- X election images
- Twitter profile images

For these rows, always store:

- whether the estimate is about all visible content or only a subset
- whether it is text or imagery
- whether it is tied to one event, query set, or hashtag set
- whether it is a prevalence estimate, a lower bound, or an inferred level

## Chart Context Standard

Every included row should be easy to summarize in one honest sentence.

Notes should make it possible to write:

- what was measured
- where
- when
- how
- why the number is still narrower than “the internet”

If those five pieces are not clear, the row is not ready.

## Preferred Balance

The final table should not become only:

- detector blogs
- only one platform
- only one year
- only academic publishing
- only media rewrites of the same few studies

Aim for a mix of:

- broader web estimates
- social-platform estimates
- publishing / professional-text estimates
- image or video estimates when they are strong enough
- audio or music-platform estimates when they are strong enough
- academic and non-academic public analysis, as long as the estimate is traceable and honestly caveated

The goal is more honest dots, not fewer perfect dots.
Be generous with inclusion when the estimate is real, narrowness is explicit, and duplication is handled cleanly.

## Known Thin Areas

These need extra attention in future sweeps:

- 2020
- 2021
- Facebook prevalence estimates, including secondary-source routes when the underlying study is hard to access
- Instagram prevalence estimates beyond narrow query-based or event-bound corpora
- broader X prevalence estimates that are not limited to one event or one modality

## Current Platform Targets

When specifically filling social-platform gaps, search for:

- Facebook:
  - long-form posts
  - public page posts
  - feed content
  - image prevalence
- Instagram:
  - feed posts
  - Reels
  - search results
  - image prevalence
- X:
  - text posts
  - images
  - profile images
  - event-specific corpora

## Refresh Output Standard

After each refresh:

- update `ai_content_meta_review.csv`
- update `ai_content_meta_review.json`
- update `ai_content_meta_review.js`
- append a concise entry to `ai_content_meta_review_refresh_log.md`

Each refresh-log entry should include:

- search scope
- exact platform or corpus lanes searched
- notable sources added
- notable rejected classes of results
- which gaps still remain thin
