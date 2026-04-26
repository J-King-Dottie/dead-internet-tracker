# Web Sample

This directory is for the full Common Crawl sampling pipeline.

The local workflow produces large month-by-month intermediate files:

- candidate CSVs
- prepared page extracts
- request payloads
- raw classifier outputs
- page-level result dumps
- run logs

Those artifacts are intentionally excluded from git.

The repo keeps lightweight methodology and setup files here. Rebuilds can regenerate the rest locally.
