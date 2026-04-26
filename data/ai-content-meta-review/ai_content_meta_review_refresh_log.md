# AI Content Meta Review Refresh Log

Use this as a lightweight running record of what each refresh actually did.

Keep it short:

- date
- search scope
- notable sources added
- notable dead ends or rejected classes of results
- gaps that still look thin

For the actual sweep standard and what context to store per estimate, use:

- `data/ai-content-meta-review/ai_content_meta_review_research_protocol.md`

## 2026-04-26 - Dead Internet Monitor Source Add

- scope: targeted review of Dead Internet Monitor after a source suggestion
- added:
  - Dead Internet Monitor / discussion posts (2026)
- notes:
  - kept as a beta multi-platform discussion-content estimate because the methodology gives a source mix and an approximate current AI content rate
  - treated as narrow discussion-content evidence, not a whole-internet estimate
- gaps still thin:
  - independent validation of broad cross-platform discussion-content prevalence estimates

## 2026-04-24 - Literature Review Upgrade

- scope: upgraded this metric from a lightweight running list to a structured literature-review workflow
- changes:
  - added a dedicated research protocol for the published-estimates chart
  - made the expected sweep explicitly academic-first plus platform-specific plus corpus-specific
  - added a required context set for every candidate estimate, including corpus, modality, denominator, sample size, time window, method type, and why the row is still narrow
  - added specific handling rules for Facebook, Instagram, and X rows so platform-specific estimates do not get stripped of context when turned into chart points
  - added explicit reject classes so traffic, recommendation, survey, and commentary results do not pollute the chart
- outcome:
  - future refreshes should behave much more like an expert literature review and less like an opportunistic source grab
- current target gaps:
  - direct Facebook prevalence estimates with accessible primary sourcing
  - direct Instagram prevalence estimates beyond narrow query-based corpora
  - broader X prevalence estimates that are not limited to one event or one modality

## 2026-04-24 - Source Criteria Loosened

- scope: recalibrated the published-estimates sweep to better match a public-analysis pulse check
- changes:
  - explicitly allowed high-quality news articles, industry research blogs, and analyst writeups when they contain references or enough method detail
  - added a source hierarchy so primary sources still win when available
  - added a deduping rule so repeated reporting of the same estimate does not create fake extra evidence
  - added explicit handling for secondary-source rows when the underlying source cannot be accessed directly
- outcome:
  - future sweeps should be broader without collapsing into junk or duplicated media echoes
- current target gaps:
  - Facebook estimates remain thin but no longer require accessible primary sourcing to be considered
  - Instagram still needs stronger prevalence estimates outside narrow query-based studies

## 2026-04-24 - Year-by-Year Expansion Pass

- scope: first pass under the stricter year-focused sweep standard, with looser but still traceable inclusion rules and explicit preference for more honest dots over fewer over-filtered ones
- added:
  - Turnitin / student papers with >=80% AI writing (2023)
  - Copyleaks / web pages (2024)
  - Turnitin / student papers with >=20% AI writing (2024)
  - AI Forensics / TikTok + Instagram top search results (2025)
  - Deezer / new music uploads (2025)
- notes:
  - platform and institutional newsroom rows were accepted when they carried a clear denominator and a defensible method story
  - the AI Forensics row uses a weighted aggregate across all annotated results because the paper reports multiple platform and country slices under one study-year
- dead ends:
  - a lot of pre-2022 web search results still collapse into commentary, predictions, or uncited summary tables
  - some appealing secondary pages turned out to be source-free rewrites once opened

## 2026-04-24 - 2026 Estimate-Year Follow-up

- scope: targeted follow-up for true 2026 estimate-year rows, plus any missing high-quality late-2025 source that materially improved the chart
- added:
  - AntiSlop / category-balanced web pages (2026)
  - Deezer / new music uploads (2026)
  - Internet Archive / newly published websites (2025)
- dead ends:
  - many 2026 papers and articles were genuinely new publications but still measured 2024 or 2025 content rather than 2026 content
  - many social-platform results were commentary about AI slop, labeling, or authenticity rather than usable prevalence estimates with a denominator
- notes:
  - 2026 remains thin in April 2026; the usable rows are still either early-year snapshots or narrow platform-specific estimates
  - the AntiSlop row uses an equal-weighted aggregate across ten same-sized content categories rather than a median, because the published category sample sizes were uniform
- gaps still thin:
  - direct 2026 Facebook prevalence estimates with a clear denominator
  - direct 2026 Instagram prevalence estimates outside narrow misinformation or hashtag corpora
  - direct 2026 X text-prevalence estimates that are not event-bound

## 2026-04-24 - Broad Public-Analysis Sweep

- scope: broad follow-up across platform-specific public analysis and accessible research pages, with explicit focus on Facebook, Instagram, X/Twitter, LinkedIn, Reddit, and Quora
- added:
  - Originality / Facebook long-form posts (2024) via a secondary writeup preserving the underlying study details after the original URL redirected
  - Originality / LinkedIn long-form posts (2024, 2025)
  - Originality / Quora answers (2024)
  - Originality / Reddit posts (2025)
  - SIMODS / Facebook AI-generated mis/disinformation (2025)
  - SIMODS / Instagram AI-generated mis/disinformation (2025)
  - SIMODS / X/Twitter AI-generated mis/disinformation (2025)
- dead ends:
  - many Instagram and Facebook results were commentary about AI slop, labeling, or user complaints rather than usable prevalence estimates
  - several results reused the same Originality numbers without adding source quality or method detail
- notes:
  - the SIMODS rows are narrow by design and were kept because the platform-specific denominator is explicit
  - the Facebook long-form-post row was kept through a secondary source because the original Originality URL now redirects away from the study
- gaps still thin:
  - direct Instagram prevalence estimates outside misinformation or narrow query-based corpora
  - broader Facebook image or feed-level prevalence estimates
  - broader X text-prevalence estimates that are not event-bound or tied to misinformation-only samples

## 2026-04-22 - Attempt 1

- scope: broad academic-first pass across arXiv, Google Scholar-style web search, and a small number of reputable secondary sources where the original source was weak or inaccessible
- added:
  - Graphite / Common Crawl annual series for new English web articles, 2020-2025
  - ACL social-media platform study
  - Stanford LLM-assisted writing across society study
  - Princeton English Wikipedia new pages study
  - biomedical abstracts study
  - OTSR journal study
  - JAMA Network Open longitudinal study
  - Spennemann active web pages estimate
  - Ahrefs new webpages estimate
  - Pangram / U.S. newspaper study
- dead ends:
  - lots of traffic, bot, referral, and usage stats that were not relevant enough to the content-share question
  - many summaries that just recycled the same Graphite claim
- thin years:
  - 2020 and 2021
  - no credible 2026 row yet

## 2026-04-22 - Attempt 2

- scope: second pass focused on stronger 2024-2025 material, plus Chinese-language search for usable studies
- added:
  - X election images study-year row
  - more JAMA subtype rows before later collapse
  - Chinese master’s-thesis study summary
  - arXiv computer science abstracts row
- dead ends:
  - most Chinese-language results were commentary, policy, or recycled media coverage rather than usable quantitative studies
  - many new hits were still detector demos or unrelated AIGC industry usage claims
- thin years:
  - 2020 and 2021 still sparse
  - 2023 still lighter than 2024-2025

## 2026-04-22 - Study-Year Consolidation

- scope: clean-up pass to enforce one value per study per year
- changes:
  - collapsed multi-row study years to one study-year value
  - used broad overall estimates where available
  - used medians where a study only offered multiple comparable sub-estimates
  - used midpoint for range-style estimates
- outcome:
  - reduced overweighting of 2025 and made the chart trend more defensible

## 2026-04-22 - Broad Follow-up

- scope: deeper academic pass, broader multilingual search, and citation chasing into platform/image/peer-review studies
- added:
  - Twitter profile images prevalence study
  - Pixiv artworks prevalence study
  - ICLR peer reviews study
  - academic peer reviews 2025 study-year row
- dead ends:
  - many promising papers discussed impact or behavior but did not provide a usable prevalence estimate
  - several papers required figure-reading for exact numbers and were skipped for now when the numeric estimate was not clean enough to justify inclusion
- thin years:
  - 2020 and 2021 remain genuinely sparse
  - 2022 is still lighter than 2024-2025

## 2026-04-24 - Thin-Year and 2026 Platform Fill Pass

- scope: targeted year-by-year follow-up aimed at the thinnest years (`2020`, `2021`, `2022`) plus genuinely new `2026` dots, with extra platform-specific attention on Quora, Walmart reviews, Google reviews, and Pinterest
- added:
  - Originality / Quora answers (`2020`, `2022`, `2023`)
  - Originality / Walmart reviews (`2020`, `2021`, `2022`)
  - Originality / Google reviews (`2023`)
  - Originality / Pinterest hiking guides (`2026`)
  - Originality / Pinterest medical diet recipes (`2026`)
- notes:
  - this pass intentionally favored thin years over adding yet more `2024` rows
  - several accepted rows are detector-based platform studies rather than academic papers, which is now explicitly allowed under the broadened public-analysis pulse-check standard
  - the new Pinterest rows are narrow but useful because they provide real `2026` estimate-year dots with clear denominators
- dead ends:
  - many `2020` and `2021` searches still collapsed into policy discussion, adoption surveys, or broad commentary rather than measurable prevalence estimates
  - many social-platform results for Facebook, Instagram, and X still repeated the same handful of studies or offered claims without a recoverable denominator
- gaps still thin:
  - direct `2021` social-platform prevalence estimates outside review or forum ecosystems
  - broader Facebook and Instagram prevalence rows that are not event-bound, misinformation-only, or dependent on a secondary writeup
  - broader `2026` X or Instagram text-prevalence estimates with a clear denominator
