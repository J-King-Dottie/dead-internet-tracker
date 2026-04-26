# Web Sample Lite

This directory stores the cheaper monthly-lite classification series.

- population source: full prepared monthly web sample in `data/web-sample/`
- lite sample: deterministic random `1,000`-page subset
- classifier: `gpt-5-mini`
- rubric: same research-guided rubric as the locked full series

This dataset is separate from the main `web-sample` series on purpose.

The month-by-month prepared files, request payloads, live outputs, page-level dumps, and run logs are kept local and excluded from git. The published summary snapshot stays in the repo because the dashboard reads it directly.
