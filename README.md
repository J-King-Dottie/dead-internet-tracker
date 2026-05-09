# Dead Internet Tracker

A one-page static research dashboard tracking public signals related to the dead internet theory: AI-generated content, AI bot traffic, bot automation, and measurable human activity on the open web.

Produced by [Dottie AI Studio](https://dottieaistudio.com.au/).

The project is deliberately cautious. It does not claim to measure the whole internet or produce one fake-precise score. It lines up recurring public signals and shows whether they point in the same direction.

Live site: [https://dead-internet-tracker.onrender.com/](https://dead-internet-tracker.onrender.com/)

## For AI Agents

Start with these files:

- [AGENTS.md](AGENTS.md): coding-agent guidance, data rules, caveats, and chart standards.
- [llms.txt](llms.txt): machine-readable summary for AI/search agents.
- [PROJECT_GOALS.md](PROJECT_GOALS.md): project intent and product constraints.
- [WEB_SAMPLE_AI_CLASSIFICATION_TEMPLATE.md](WEB_SAMPLE_AI_CLASSIFICATION_TEMPLATE.md): Common Crawl AI-content classification rubric.
- [data/dashboard_readable.json](data/dashboard_readable.json): normalized chart data and latest plotted values.
- [index.html](index.html): static public page.

Agent summary:

```text
static dashboard -> local snapshot data -> transparent public proxies
-> cautious chart copy -> no live browser API calls
```

## What This Site Measures

- AI-generated or AI-influenced content estimates from recurring public reports and curated research.
- Monthly Common Crawl samples of article-style open-web pages classified for AI writing signals.
- Cloudflare Radar AI bot traffic as a proxy for AI systems crawling and traversing the public web.
- Wikipedia editor activity as a proxy for sustained human contribution to open knowledge.
- Stack Overflow question volume as a proxy for public human-to-human software help.
- Imperva bot reports as narrower security-focused automation signals.

## Important Caveats

- This page does not measure the whole internet.
- Cloudflare sees a large but incomplete slice of the public web, not the whole internet.
- Imperva data is security-focused and is not directly comparable to Cloudflare.
- Common Crawl samples are article-style open-web pages, not all pages.
- Published AI-content estimates come from different studies and content sets, so levels are noisy.
- The dashboard compares signal direction; it is not a universal "dead internet" index.

## Repository Layout

- `index.html`: public static page.
- `data/`: published snapshots consumed by the page.
- `scripts/`: refresh scripts for rebuilding snapshots.
- `research/`: source notes and supporting research artifacts.
- `.github/workflows/refresh-data.yml`: scheduled snapshot refresh workflow.
- `.github/workflows/collect-github-traffic.yml`: repository traffic tracking.
- `render.yaml`: Render static-site blueprint.

## Snapshot Data

- [Machine-readable normalized chart data](https://dead-internet-tracker.onrender.com/data/dashboard_readable.json)
- [Cloudflare AI bot traffic](https://dead-internet-tracker.onrender.com/data/cloudflare/cloudflare.json)
- [Wikipedia activity](https://dead-internet-tracker.onrender.com/data/wikipedia/wikipedia.json)
- [Stack Overflow activity](https://dead-internet-tracker.onrender.com/data/stackoverflow/stackoverflow.json)
- [Imperva traffic profile](https://dead-internet-tracker.onrender.com/data/imperva/imperva.json)
- [AI content meta-review](https://dead-internet-tracker.onrender.com/data/ai-content-meta-review/ai_content_meta_review.json)
- [Common Crawl lite web sample summary](https://dead-internet-tracker.onrender.com/data/web-sample-lite/web_sample_lite_summary.json)

## Local Preview

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

## Refreshing Data

Examples:

```bash
python3 scripts/refresh_stackoverflow.py
python3 scripts/refresh_wikipedia.py
python3 scripts/refresh_cloudflare.py
python3 scripts/build_dashboard_readable.py
python3 scripts/embed_dashboard_readable.py
```

Some research pipelines write large intermediate files locally. Those are intentionally gitignored. The repo keeps the published snapshots and methodology, not every working artifact.

## GitHub Traffic Tracking

The repo includes `.github/workflows/collect-github-traffic.yml` and `scripts/collect_github_traffic.py`.

It saves:

- daily clone counts and unique cloners
- daily view counts and unique visitors
- daily snapshots of popular paths
- daily snapshots of popular referrers

The workflow needs a `TRAFFIC_TOKEN` repository secret with access to GitHub traffic APIs.

## Discovery Keywords

`dead internet theory`, `AI-generated content`, `AI content estimates`, `AI bot traffic`, `AI crawlers`, `bot automation`, `Cloudflare Radar`, `Imperva bad bot report`, `Common Crawl`, `web sample classification`, `Wikipedia activity`, `Wikipedia editors`, `Stack Overflow questions`, `human web activity`, `synthetic media`, `public web measurement`, `internet automation`.

## Deploying to Render

This repo includes a root `render.yaml` for a static-site deploy. Connect the GitHub repo in Render and deploy it as a Blueprint or Static Site.
