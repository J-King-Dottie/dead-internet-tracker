#!/usr/bin/env bash
set -euo pipefail

public_dir="public"

python3 scripts/embed_dashboard_readable.py

files=(
  "index.html"
  "robots.txt"
  "sitemap.xml"
  "llms.txt"
  "favicon.svg"
  "site.webmanifest"
  "social-preview.svg"
  "social-preview.png"
  "README.md"
  "WEB_SAMPLE_AI_CLASSIFICATION_TEMPLATE.md"
  "LICENSE"
  "data/dashboard_readable.json"
  "data/cloudflare/cloudflare.json"
  "data/cloudflare/cloudflare.js"
  "data/imperva/imperva.json"
  "data/imperva/imperva.js"
  "data/wikipedia/wikipedia.json"
  "data/wikipedia/wikipedia.js"
  "data/stackoverflow/stackoverflow.json"
  "data/stackoverflow/stackoverflow.js"
  "data/ai-content-meta-review/ai_content_meta_review.json"
  "data/ai-content-meta-review/ai_content_meta_review.js"
  "data/web-sample/web_sample_dashboard_snapshot.json"
  "data/web-sample/web_sample_dashboard_snapshot.js"
  "data/web-sample-lite/web_sample_lite_summary.json"
  "data/web-sample-lite/web_sample_lite_summary.js"
)

rm -rf "$public_dir"

for file in "${files[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing required static asset: $file" >&2
    exit 1
  fi

  mkdir -p "$public_dir/$(dirname "$file")"
  cp "$file" "$public_dir/$file"
done

echo "Static dashboard build prepared in $public_dir."
