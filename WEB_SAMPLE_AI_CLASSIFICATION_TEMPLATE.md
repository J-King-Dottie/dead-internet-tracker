# Web Sample AI Classification Template

## Objective

Build and refresh a repeatable time-series estimate of:

`What share of sampled open-web article-like pages whose URLs suggest publication in a target month appear to be all human, show some evident AI writing, or show a strong signal of AI writing?`

This is not a census of the internet.

It is a stable repeated sample using the same filtering, extraction, and classification method over time.

## Core Principle

Keep this simple.

The value of this metric is:

- one stable publication-month URL filter
- one stable Common Crawl crawl-selection rule
- one random monthly sample
- one fixed excerpt rule
- one stable model judgment
- one stable request size and live API concurrency

If those stay fixed, the trend is meaningful even if the classifier is imperfect.

## Scope

Target:

- open-web written pages
- mostly long-form text pages
- article-like or blog-like pages whose URLs suggest they were published in the target month

Do not include in v1:

- Reddit
- X / Twitter
- Facebook
- other closed platforms with messy or inconsistent access

Use Common Crawl as the source corpus.

## Short Method Summary

- use the first Common Crawl snapshot whose crawl window starts after the target month ends
- filter for article-like URLs with a target year+month signal in the URL path
- keep one random URL per registered domain
- randomly sample `10,000` initial candidate URLs
- fetch the exact Common Crawl WARC record and extract the main readable text
- keep pages with at least `400` tokens of readable text
- keep the first `1,000` tokens
- stop once `5,000` usable pages have been reached
- if the first `10,000` candidates fall short, top up in `2,000`-candidate chunks from the same crawl before moving to later crawls

## Sampling Frame

Define the population using broad article-like URL rules plus a target month/year URL rule.

Article-like signals include URLs matching at least one of these patterns:

- dated article URLs like `/2026/03/`
- `/blog/`
- `/blogs/`
- `/article/`
- `/articles/`
- `/news/`
- `/post/`
- `/posts/`
- `/story/`
- `/stories/`

Exclude obvious non-content paths:

- `/tag/`, `/tags/`
- `/category/`, `/categories/`
- `/author/`, `/authors/`
- `/search/`
- `/archive/`, `/archives/`
- `/feed/`, `/feeds/`
- `/video/`, `/videos/`
- `/gallery/`, `/galleries/`
- `/login/`, `/signin/`, `/account/`
- `/checkout/`, `/cart/`
- `/product/`, `/products/`, `/shop/`
- `/docs/`, `/documentation/`, `/wiki/`
- `/forum/`, `/forums/`
- `/profile/`, `/profiles/`

For the target publication month, require a year+month signal in the URL path, in common forms such as:

- `/YYYY/MM/`
- `/YYYY/MM/DD/`
- `YYYY-MM`
- `YYYY-MM-DD`
- `YYYY_MM`
- `YYYYMMDD`

We care about the target month and year, not the day.

The filter should stay broad and dumb. Do not keep tweaking it.

## Common Crawl Querying

For bulk filtering, use the Common Crawl columnar index, not the public URL index server.

Why:

- Common Crawl explicitly recommends the columnar index for bulk filtering and aggregation
- the public URL index server is fine for individual lookups, not this volume

Preferred query path:

- register the Common Crawl columnar index in AWS Athena
- run the SQL query against the first Common Crawl snapshot whose crawl window starts after the target month ends
- export the sampled rows as CSV

The query should:

- use the first Common Crawl snapshot whose crawl window starts after the target month ends
- if that is not enough, pull additional candidates from that same crawl first
- only then move forward to the next later crawl(s)
- only fall back backward when no later crawl exists yet
- keep only `fetch_status = 200`
- keep only `content_mime_detected = 'text/html'`
- keep only likely English pages
- apply the inclusion and exclusion URL rules
- require a target year+month signal in the URL path
- keep one random URL per registered domain
- randomly sample `10,000` candidate rows from what remains

One URL per registered domain is intentional. It stops a few giant sites from dominating the run.

## Sample Size

Default:

- `10,000 candidate URLs per month`
- target `5,000 usable pages per month`

Reason:

- strong enough monthly signal
- still cheap with `gpt-5-mini`
- operationally realistic

Approximate 95% margin of error for a simple binary share estimate:

- `5,000` usable pages: about `+/-1.4 percentage points`

This only describes sampling error inside the sampled frame. Real-world crawl bias and classifier error still matter.

## Page Handling

For each sampled URL:

1. fetch the exact Common Crawl WARC record, not the live page
2. extract the HTML response body
3. extract the main readable text
4. keep pages with at least `400` tokens of readable text
5. keep the first `1,000` tokens
6. classify that excerpt as `Human`, `Mixed`, or `AI`

If a page is too short, broken, or mostly boilerplate, drop it and note the drop count.
If the first `10,000` candidates do not produce `5,000` usable pages, top up in `2,000` candidate chunks from the same crawl until `5,000` usable pages are reached. Append those additional candidates into the same candidate CSV rather than creating separate top-up data files. Only move to the next later crawl if the current crawl still does not yield enough.
During local prep, stop fetching and extracting as soon as `5,000` usable pages have been reached. Do not process the rest of a top-up chunk unnecessarily.

## Classifier Prompt

Keep the prompt very simple.

Current locked rubric id:

- `research-guided-rubric-v3`

Use a forced choice:

- `Human`
- `Mixed`
- `AI`

Prompting principle:

- choose `Human` when the writing appears to be all human
- choose `Mixed` when some level of AI writing appears evident
- choose `AI` when there is a strong signal of AI writing
- judge the writing itself, not the topic
- use a research-guided rubric that weighs:
  - lexical variety and repetition
  - sentence and syntactic variation
  - discourse cohesion and progression
  - readability and register
  - personal reference or concrete specificity
- provide simple supporting metrics with each excerpt:
  - lexical diversity
  - repeated 3-gram rate
  - sentence-length standard deviation
- metrics are supporting evidence only, not an automatic override
- useful signals toward `AI` can include unusually standardized or impersonal register, repetitive phrasing, flatter sentence rhythm, smooth but generic progression, and repeated templated discourse-marker openings
- personal reference or concrete specificity can support `Human`, but their absence alone is not enough for `AI`
- judge patterns across the excerpt, not one phrase in isolation
- do not rely on first-person pronouns, contractions, family references, or minor grammatical roughness as stand-alone evidence for `Human`
- do not treat polished, factual, or generic writing by itself as enough for `AI`
- no single cue is decisive
- do not use `Mixed` as a fallback for uncertainty

Do not over-specify style rules. The point is stable judgment, not an essay about the judgment.

## Published Basis for the Rubric

This rubric is not invented from scratch.

It is a lightweight operationalization of feature families that recur across published comparisons of human and AI-generated writing.

Core papers used here:

- [Opara 2025, *Distinguishing AI-Generated and Human-Written Text Through Psycholinguistic Analysis*](https://arxiv.org/abs/2505.01800)
  - useful for an interpretable cue framework linking stylometric features to lexical retrieval, discourse planning, cognitive load management, and self-monitoring
- [Fredrick and Craven 2025, *Lexical diversity, syntactic complexity, and readability: a corpus-based analysis of ChatGPT and L2 student essays*](https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2025.1616935/full)
  - useful for lexical diversity, syntactic complexity, readability, and communicative appropriateness
- [Muñoz-Ortiz et al. 2024, *Contrasting Linguistic Patterns in Human and LLM-Generated News Text*](https://link.springer.com/article/10.1007/s10462-024-10903-2)
  - useful for cross-model evidence that human text shows more scattered sentence-length distributions and more varied vocabulary, while LLM text differs in systematic lexical and syntactic distributions
- [Georgiou 2025, *Differentiating Between Human-Written and AI-Generated Texts Using Automatically Extracted Linguistic Features*](https://www.mdpi.com/2078-2489/16/11/979)
  - useful for pronoun/function-word versus nominal-density contrasts and for keeping the rubric anchored in interpretable linguistic features
- [Emara 2025, *A linguistic comparison between ChatGPT-generated and nonnative student-generated short story adaptations: a stylometric approach*](https://slejournal.springeropen.com/articles/10.1186/s40561-025-00388-z)
  - useful for repeated `as ...` and `with ...` openings, adjective-heavy descriptive language, and the contrast between smoother AI coherence and deeper human plot variation
- [Dou et al. 2022, *Scarecrow: A Framework for Scrutinizing Machine Text*](https://aclanthology.org/2022.acl-long.501/)
  - useful as a reminder that machine text quality problems often appear as distributed patterns such as redundancy and incoherence, not one magic marker
- [Jakesch et al. 2023, *Human heuristics for AI-generated language are flawed*](https://pubmed.ncbi.nlm.nih.gov/36881628/)
  - useful for what not to do: first-person pronouns, contractions, family topics, and similar folk heuristics are not reliable stand-alone signals

## Source-Backed Rubric Rationale

Keep the rubric tied to cue families that have direct support in the literature.

### 1. Lexical variety and repetition

Support:

- Opara maps lexical features to lexical retrieval and self-monitoring.
- Fredrick and Craven compare TTR, MTLD, and Voc-D directly.
- Muñoz-Ortiz et al. find broader distributional lexical differences between human and LLM news writing.

Use in rubric:

- lower variety, repeated wording, or homogenized phrasing can support `Mixed` or `AI`
- advanced vocabulary alone is not enough for `AI`

### 2. Sentence and syntactic variation

Support:

- Opara treats sentence and structural features as interpretable authorship cues.
- Fredrick and Craven compare Mean Length of T-Unit and Dependent Clauses per T-Unit.
- Muñoz-Ortiz et al. report that human writing shows more scattered sentence-length distributions than LLM outputs.

Use in rubric:

- flatter rhythm or overly standardized structural pacing can support `Mixed` or `AI`
- syntactic complexity alone is not enough for `AI`

### 3. Discourse cohesion and progression

Support:

- Opara explicitly links stylometric evidence to discourse planning.
- Dou et al. show that machine text quality problems often surface through distributed issues such as redundancy and incoherence.
- Emara finds AI text smoother and more formulaically coherent, while student text diverges more in plot, context, and development.

Use in rubric:

- smooth but generic progression, repetitive transitions, or shallow development can support `Mixed` or `AI`
- one odd sentence is not enough; look for an excerpt-level pattern

### 4. Readability and register

Support:

- Fredrick and Craven find AI-generated essays more linguistically dense and harder to read on Flesch-Kincaid and Gunning-Fog.
- Georgiou finds AI text more content-word and nominal-density heavy, while human text leans more on function words and pronouns.
- Emara finds AI text more descriptive, adjective-heavy, and complex.

Use in rubric:

- unusually standardized, impersonal, or over-smoothed register can support `Mixed` or `AI`
- polished grammar or factual tone alone is not enough for `AI`

### 5. Personal reference and concrete specificity

Support:

- Opara includes first-person count and direct address among interpretable features.
- Georgiou reports that human texts lean more on pronouns and other function-word patterns than AI text.
- Jakesch et al. show that personal-sounding features are easy to overtrust if treated as a single heuristic.

Use in rubric:

- personal reference, situated detail, and concrete specificity can support `Human`
- their absence is not enough for `AI`
- first-person pronouns or contractions alone should not decide the label

## Guardrails from the Literature

- Do not use one folk heuristic as a shortcut.
  - Jakesch et al. show that humans over-trust cues like first-person pronouns, contractions, and family references.
- Do not turn the rubric into a hard detector.
  - Muñoz-Ortiz et al. and Georgiou both work in specific domains and populations. Their findings are useful, but domain-sensitive.
- Do not let one metric decide the label.
  - The metrics here are supporting evidence only.
- Do not let one striking phrase decide the label.
  - Scarecrow and related stylometric work point toward distributed patterns, not a single giveaway sentence.

## Phrase-Level Examples

These are illustrative examples only. They are not templates and they are not exhaustive.

- repeated `as ...` or `with ...` openings
  - Emara reports these as noticeably more frequent in the AI texts she studied
- repeated templated discourse openings or connective framing
  - treat this as a supporting cue when it appears as a repeated pattern across the excerpt
- repeated stock descriptive phrasing
  - also a supporting cue only, especially when paired with flatter rhythm or generic progression

## Why This Stays a Rubric, Not a Hard Detector

So:

- the rubric uses published cue families rather than ad hoc internet lore
- the simple metrics are only supporting evidence
- no single metric or stylistic cue should decide the label by itself
- the saved metadata should include the rubric version and prompt hash
## Model and Request Design

Use:

- `gpt-5-mini`
- direct OpenAI Responses API calls

Request shape:

- `20` excerpts per request
- `250` requests for a `5,000` page monthly run
- `10` concurrent live requests

Why `20`:

- much cleaner than one request per page
- safer and easier to validate than trying to cram `50` pages into one request
- keeps each request comfortably sized
- still gives fast wall-clock time when run concurrently

Output handling:

- use strict JSON schema output
- give the model enough output headroom that token limits do not become the failure point
- write results incrementally so runs can resume without losing prior completed requests

## Cost

Using OpenAI's published pricing for `gpt-5-mini`:

- standard input: `$0.25 / 1M tokens`
- standard output: `$2.00 / 1M tokens`

At this size, model cost is not the bottleneck.

The heavier operational cost is:

- Common Crawl querying
- WARC fetching
- HTML cleaning
- failed pages

## Output

Save both page-level results and aggregate summaries.

### Page-level data

| period | url | domain | sample_source | excerpt | classification |
|---|---|---|---|---|---|

Keep the excerpt that was actually classified. That lets us re-run the same sample later if we ever intentionally change methodology.

### Aggregate summary

| period | sample_size | ai_count | mixed_count | human_count | ai_share | ai_influenced_share | notes |
|---|---:|---:|---:|---:|---:|---:|---|

This summary file is what the dashboard should read.

## Stability Rules

Do not casually change:

- source corpus
- target-month URL rules
- crawl-selection rule
- one-URL-per-domain rule
- excerpt length
- prompt
- model
- request grouping
- live concurrency

If one of those changes, note a methodology break.

## Refresh Process

Each refresh should:

1. render the Athena SQL for the target month using the saved Common Crawl month map
2. run the query against the first Common Crawl snapshot whose crawl window starts after the target month ends and export the first `10,000` candidate rows
3. fetch and extract the sampled pages
4. if needed, top up with additional `2,000` candidate chunks from the same crawl until `5,000` usable pages are reached, appending those rows into the same candidate CSV
5. only if the current crawl still falls short, move to the next later crawl and repeat the top-up logic
6. build the OpenAI request JSONL
7. run the live direct API classifier with `20` excerpts per request and `10` concurrent requests
8. apply the labels back onto the page rows
9. update the aggregate summary, including `AI share`, `Mixed share`, and `AI-influenced share`
10. append a short refresh note

## Sources

- Common Crawl overview: [Common Crawl Overview](https://commoncrawl.org/overview)
- Common Crawl columnar index: [Columnar Index](https://commoncrawl.org/columnar-index)
- Common Crawl CDXJ index: [CDXJ Index](https://commoncrawl.org/cdxj-index)
- OpenAI pricing: [OpenAI API pricing](https://openai.com/api/pricing)
- GPT-5 mini model page: [GPT-5 mini](https://platform.openai.com/docs/models/gpt-5-mini)
- Psycholinguistic stylometric framework: [Opara 2025](https://arxiv.org/abs/2505.01800)
- Lexical, syntactic, and readability comparison: [Fredrick and Craven 2025](https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2025.1616935/full)
- Cross-model news-domain comparison: [Muñoz-Ortiz et al. 2024](https://link.springer.com/article/10.1007/s10462-024-10903-2)
- Interpretable linguistic feature comparison: [Georgiou 2025](https://www.mdpi.com/2078-2489/16/11/979)
- Phrase-level and discourse-opening comparison: [Emara 2025](https://slejournal.springeropen.com/articles/10.1186/s40561-025-00388-z)
- Distributed machine-text error framework: [Dou et al. 2022, Scarecrow](https://aclanthology.org/2022.acl-long.501/)
- Heuristic caution: [Jakesch et al. 2023](https://pubmed.ncbi.nlm.nih.gov/36881628/)

