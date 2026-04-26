# Dead Internet Tracker

Project guide for coding agents working in this repo.

## Goal

Build a one-page dashboard about the Dead Internet Theory using a mix of:

- direct public metrics
- public proxies
- manually compiled recurring reports

The point is not to produce one fake-precise score. The point is to line up the best available signals and show whether they point the same way.

## Product Shape

- Static frontend at runtime
- No live API calls in the browser
- All data is precomputed and saved into local snapshot files
- Dashboard reads local snapshot JS files
- Small data only: annual or monthly summary points

## Current Data Pattern

Each real metric should follow this structure:

- refresh script in `scripts/`
- saved snapshot in `data/<metric>/...`
- browser-loadable snapshot in `data/<metric>/...`
- frontend chart reads only the saved snapshot

Examples:

- `scripts/refresh_stackoverflow.py`
- `scripts/refresh_wikipedia.py`
- `scripts/refresh_cloudflare.py`

## Current Metrics

Direct / stronger:

- Stack Overflow activity
- Wikipedia activity
- Cloudflare AI bot share of total traffic

Still placeholder or future work:

- referrals / search-social-AI displacement
- common crawl publication-month sampling and classification
- reported estimates / research meta-analysis

## Web Sample Metric

The web-sample metric is now a locked recurring process:

- Common Crawl columnar index through Athena
- publication-month approximation from URL year+month patterns
- first Common Crawl snapshot whose crawl window starts after the target month ends, with same-crawl top-ups before later crawls
- one URL per registered domain
- `10,000` initial candidates, then `2,000` same-crawl top-ups if needed
- `5,000` usable pages after main-text extraction
- `400–1000` token excerpt window
- `gpt-5-mini` classifier
- direct live Responses API calls
- `20` excerpts per request
- `10` concurrent requests

Classifier labels:

- `Human`
- `Mixed`
- `AI`

Prompting uses a short rubric with source-backed cues and lightweight supporting metrics. The methodology details live in:

- `WEB_SAMPLE_AI_CLASSIFICATION_TEMPLATE.md`

## Chart Rules

- Keep charts simple
- Prefer one clear takeaway per card
- If a metric gets too caveat-heavy, simplify the visual before adding more layers
- Default to annual chart points unless monthly detail is necessary for projection logic
- Tooltip copy should be short, human, and honest
- Do not imply a metric is broader than it is

## Data Rules

- Prefer direct public data where possible
- If direct data does not exist, use a proxy only if the tooltip explains what it actually measures
- Public reports are allowed if they recur and can be manually compiled over time
- Label compiled-report metrics as estimates or reported figures, not direct telemetry
- Never silently change a metric’s denominator or scope

## Cloudflare Rules

- Cloudflare data is a proxy, not the whole internet
- Human wording for caveat:
  `Cloudflare sees a large but incomplete slice of the public web, not the whole internet.`
- Avoid overstating what Cloudflare measures
- Distinguish:
  - bot share of total traffic
  - AI bot share of total traffic
  - AI crawler share of bot traffic

## Projection Rules

Use simple, explainable projections:

- latest year can be projected from partial-year monthly data
- prefer seasonal adjustment using recent full years
- backfill partial first years only when necessary
- always mention when a year is projected or partly backfilled

## Copy Rules

- Write like a person
- Short sentences
- No inflated certainty
- No “magic number” language
- If a metric is narrow, say so plainly

## Design Module

This project can use a `DESIGN.md` alongside `AGENTS.md` when a stronger UI direction is needed.

Reference:

- [VoltAgent awesome-design-md](https://github.com/VoltAgent/awesome-design-md)

Useful framing from that project:

- `AGENTS.md` tells coding agents how to build the project
- `DESIGN.md` tells design agents how the project should look and feel

If design work gets messy, add a root-level `DESIGN.md` rather than burying visual rules in code comments.

## Working Style

- Make the smallest honest claim the data supports
- Keep architecture boring
- Save data locally
- Prefer fewer, clearer charts over more clever charts
- When unsure, choose the version that is easier to explain in one sentence
