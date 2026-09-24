#!/usr/bin/env bash
set -euo pipefail

public_dir="public"

files=(
  "index.html"
  "googlebf976655431cae89.html"
  "robots.txt"
  "sitemap.xml"
  "llms.txt"
  "favicon.svg"
  "site.webmanifest"
  "social-preview.svg"
  "social-preview.png"
  "README.md"
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

# Each Render deployment must advertise its own URL, including in embedded data.
# Keep source snapshots unchanged so both services can build from the same branch.
site_url="${RENDER_EXTERNAL_URL:-https://dead-internet.onrender.com}"
site_url="${site_url%/}"
if [[ ! "$site_url" =~ ^https://[a-zA-Z0-9.-]+$ ]]; then
  echo "Expected an HTTPS hostname in RENDER_EXTERNAL_URL." >&2
  exit 1
fi
for file in index.html robots.txt sitemap.xml llms.txt README.md data/dashboard_readable.json; do
  sed -i "s|https://dead-internet.onrender.com|$site_url|g" "$public_dir/$file"
done

# Report the last committed page/data change, not the deploy date. Traffic-log
# updates and infrastructure-only commits should not claim the page changed.
# Render's shallow checkout otherwise makes every file look newly committed.
if [[ "$(git rev-parse --is-shallow-repository)" == "true" ]]; then
  # Render removes the origin remote after checkout; this repository is public.
  git fetch --unshallow --quiet https://github.com/J-King-Dottie/dead-internet-tracker.git main
fi
last_modified="$(git log -1 --format=%cs -- index.html data)"
if [[ "$last_modified" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  sed -i "s|<lastmod>[^<]*</lastmod>|<lastmod>$last_modified</lastmod>|" "$public_dir/sitemap.xml"
else
  echo "Cannot determine the dashboard modification date from Git history." >&2
  exit 1
fi

echo "Static dashboard build prepared in $public_dir."
