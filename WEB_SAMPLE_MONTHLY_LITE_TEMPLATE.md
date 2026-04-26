# Web Sample Monthly Lite Template

## Objective

Build a cheaper monthly classification series that preserves the locked web-sample methodology as much as possible.

This is a separate series from the full `5,000`-page run.

It should answer:

`What share of a stable monthly sample of article-style open-web pages shows detectable AI-writing signals?`

## Core Rule

Do not replace the locked full method.

The lite series is a cheaper readout built from the full prepared sample.

## Method

- start from the existing `5,000`-page prepared monthly sample
- draw a deterministic random sample without replacement
- default to `1,000` pages per month
- keep the same excerpts, metrics, rubric, model, batch size, and concurrency settings
- classify the subset live with `gpt-5-mini`
- save outputs in `data/web-sample-lite/`

## Deterministic Sampling

The random draw should be stable and reproducible.

- sort pages by id first
- seed the sample from period plus sample size
- do not hand-pick pages
- do not oversample longer pages

## Output Files

For each period:

- `web_sample_lite_prepared_<period>.json`
- `web_sample_lite_requests_<period>.jsonl`
- `web_sample_lite_live_output_<period>.jsonl`
- `web_sample_lite_page_level_<period>.json`

Series-level outputs:

- `web_sample_lite_summary.json`
- `web_sample_lite_summary.js`

## Year Setup

Prepare one year at a time:

```bash
python scripts/setup_web_sample_lite_year.py --year 2020
```

This should only prepare samples and request files.

It should not call the API.

## Live Run

Run a prepared month explicitly:

```bash
python scripts/run_web_sample_live.py ^
  --input data/web-sample-lite/web_sample_lite_requests_2020-01.jsonl ^
  --data-dir data/web-sample-lite ^
  --output-prefix web_sample_lite_live_output ^
  --error-prefix web_sample_lite_live_errors ^
  --suffix 2020-01
```

## Apply Results

Apply one completed month back into the lite dataset:

```bash
python scripts/apply_web_sample_lite_results.py ^
  --prepared data/web-sample-lite/web_sample_lite_prepared_2020-01.json ^
  --output data/web-sample-lite/web_sample_lite_live_output_2020-01.jsonl
```

## Caveat

This is still not the whole internet.

It is a repeated sample of article-style open-web pages. The lite series is useful because it is cheaper and faster, but it is noisier than the full series.
