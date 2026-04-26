# Project Goal

Build an HTML dashboard that tracks signals related to the Dead Internet Theory across time.

The dashboard currently has two broad areas:

1. Internet traffic and navigation
2. Internet content generation

# Confirmed Metric Ideas

- Cloudflare Radar: bot vs human traffic
- StatCounter: search vs social vs AI chatbot referrals
- Wikimedia / Wikipedia: edits or editor activity over time
- Stack Overflow / Stack Exchange activity over time: people are still posting, but question activity has dropped sharply, especially after 2022, making it a useful proxy for declining human-to-human problem solving on the web
- Common Crawl publication-month sample + fixed classifier pipeline: sample a fixed number of article-like pages whose URLs suggest publication in the target month, classify them with the same GPT-5 mini rubric each run, and track the results over time so the trend stays meaningful even if the classifier is imperfect
- Recurring AI deep research job: scrape published estimates of AI-generated content share, normalize them, and store them as a time-series dataset so the dashboard reflects the evolving consensus and disagreement over time
- Signal consensus dashboard: classify each metric with fixed rules and report how many of the tracked signals currently point toward a stronger dead internet trend
