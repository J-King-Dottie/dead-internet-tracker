# Dead Internet Tracker

Dead Internet Tracker is a one-page research dashboard for the **dead internet theory**. It compares public signals of AI-generated content, AI bot traffic, and human activity on the web over time.

The charts show what each source actually measures. They do not estimate a single percentage of the internet that is "dead."

**Live dashboard:** https://dead-internet.onrender.com/

Built by [Dottie AI Studio](https://dottieaistudio.com.au/).

## What the charts cover

- **AI content:** published estimates from different studies and platforms.
- **Automated traffic:** Cloudflare Radar AI bot traffic and Imperva bot reports.
- **Human activity:** Wikipedia editor activity and Stack Overflow questions.

These are separate signals, not interchangeable measurements. Cloudflare sees a large but incomplete slice of the public web, not the whole internet. AI content estimates use different samples and methods.

## Data and code

The dashboard is static: the browser reads saved snapshots in [`data/`](data/) and makes no live data API calls. [`data/dashboard_readable.json`](data/dashboard_readable.json) contains the plotted series in one machine-readable file. Refresh scripts are in [`scripts/`](scripts/).

For coding agents, start with [`AGENTS.md`](AGENTS.md) for project rules and [`llms.txt`](llms.txt) for a concise data guide. [`index.html`](index.html) is the dashboard.

## Run locally

```bash
python3 -m http.server 8000
```

Open http://localhost:8000. To update a metric, run its `scripts/refresh_*.py` script, then rebuild the readable snapshot with `python3 scripts/build_dashboard_readable.py` and `python3 scripts/embed_dashboard_readable.py`.

## Security rebuild — 24 October 2026

This dashboard publishes static assets and does not use Node.js or PHP in its
application build/runtime. The Render build script makes an HTTPS Git request
when its checkout is shallow, so the eMudhra advisory still requires a fresh
Render build to refresh the native certificate store. No app dependency update
is required for that Bash/Git build.

The GitHub workflows use maintained checkout/setup-python actions on the Node 24
action runtime; GitHub manages the runner's embedded runtime and system trust.
Verified locally: the static publish build, Bash syntax and all 19 Python tests.
Source preparation is based on current origin/main 9200939 in a separate
security worktree, preserving the original checkout's existing changes.

Deployment remains pending: connect Render, confirm the matching static service
(and any other service using this same repository), clear the build cache and
rebuild. Verify the deployed source, pages and build logs. No deploy, data refresh
or push was performed during this preparation.
