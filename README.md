# Dead Internet Tracker

One-page static dashboard for tracking public signals related to the Dead Internet Theory.

The site ships as plain HTML plus local snapshot files. There are no live browser API calls at runtime.

## What is in the repo

- `index.html`: the dashboard
- `data/`: published snapshots consumed by the dashboard
- `scripts/`: refresh scripts for rebuilding those snapshots
- `render.yaml`: Render static-site blueprint

## Local preview

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

## Refreshing data

Examples:

```bash
python3 scripts/refresh_stackoverflow.py
python3 scripts/refresh_wikipedia.py
python3 scripts/refresh_cloudflare.py
```

Some research pipelines write large intermediate files locally. Those are intentionally gitignored. The repo keeps the published snapshots and methodology, not every working artifact.

## Deploying to Render

This repo includes a root `render.yaml` for a static-site deploy. Connect the GitHub repo in Render and deploy it as a Blueprint or Static Site.
