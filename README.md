# Dead Internet Tracker

A one-page static research dashboard tracking public signals related to the dead internet theory: AI-generated content, AI bot traffic, bot automation, and measurable human activity on the open web.

Produced by [Dottie AI Studio](https://dottieaistudio.com.au/).

The project is deliberately cautious. It does not claim to measure the whole internet or produce one fake-precise score. It lines up recurring public signals and shows whether they point in the same direction.

Live site: [https://dead-internet-tracker.onrender.com/](https://dead-internet-tracker.onrender.com/)

## Project Goal

Build a static HTML dashboard that tracks signals related to the Dead Internet Theory across time.

The dashboard has two broad areas:

- Internet traffic and navigation.
- Internet content generation.

The core product goal is signal comparison, not a single score. Each metric should make the smallest honest claim its source supports.

## For AI Agents

Start with these files:

- [AGENTS.md](AGENTS.md): coding-agent guidance, data rules, caveats, and chart standards.
- [llms.txt](llms.txt): machine-readable summary for AI/search agents.
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

## Metric Roadmap

Confirmed or planned metric ideas:

- Cloudflare Radar bot and AI bot traffic.
- Search, social, and AI chatbot referrals, if a recurring public source can be maintained.
- Wikimedia / Wikipedia edits or editor activity over time.
- Stack Overflow / Stack Exchange activity over time, especially question volume after 2022.
- Common Crawl publication-month samples with a fixed classifier pipeline, so trend movement is meaningful even if individual classifications are imperfect.
- A recurring AI-content research review that normalizes published estimates into a time-series dataset.
- A signal consensus view that reports how many tracked signals point toward a stronger dead internet trend under fixed rules.

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

## Discovery Keywords

`dead internet theory`, `AI-generated content`, `AI content estimates`, `AI bot traffic`, `AI crawlers`, `bot automation`, `Cloudflare Radar`, `Imperva bad bot report`, `Common Crawl`, `web sample classification`, `Wikipedia activity`, `Wikipedia editors`, `Stack Overflow questions`, `human web activity`, `synthetic media`, `public web measurement`, `internet automation`.

## Deploying to Render

This repo includes a root `render.yaml` for a static-site deploy. Connect the GitHub repo in Render and deploy it as a Blueprint or Static Site.

Render does not refresh data or install Python dependencies during deploy. GitHub Actions prepares the static files; Render runs `scripts/render_build.sh` to copy the committed site assets into `public`.
