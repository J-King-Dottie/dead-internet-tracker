#!/usr/bin/env bash
set -euo pipefail

public_dir="public"

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

python3 - <<'PY'
import json
from pathlib import Path

index_path = Path("public/index.html")
data_path = Path("data/dashboard_readable.json")

dashboard_data = json.loads(data_path.read_text(encoding="utf-8"))
payload = json.dumps(dashboard_data, ensure_ascii=False, separators=(",", ":")).replace(
    "</script>",
    "<\\/script>",
)
block = (
    '  <script type="application/json" id="dashboard-readable-data">\n'
    f"{payload}\n"
    "  </script>\n"
)

html = index_path.read_text(encoding="utf-8")
if 'id="dashboard-readable-data"' in html:
    raise SystemExit("dashboard-readable-data is already embedded in public/index.html")
if "</head>" not in html:
    raise SystemExit("Cannot embed dashboard-readable-data because </head> was not found")

index_path.write_text(html.replace("</head>", block + "</head>", 1), encoding="utf-8")
PY

echo "Static dashboard build prepared in $public_dir."
