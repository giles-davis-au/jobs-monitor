# Sydney Tech Jobs Monitor — Design & Implementation Plan

## Context

You want a personal tool that watches the careers pages of a configurable list of
tech companies, detects newly-posted Sydney-relevant roles, and emails you when a
job title matches your keyword list. This document is the result of a joint
design pass: clarifying requirements, live-investigating how each of your 10
target companies actually exposes job data (not guessing — every finding below
was confirmed against the real site today), and proposing the simplest
architecture that stays reliable and is cheap to extend to company #11, #12, etc.

Decisions already locked in with you:
- **Runtime**: local Mac, scheduled via `launchd` (not cloud).
- **Notification**: email.
- **Match scope (v1)**: job **title** only, against a keyword list you maintain.
- **Frequency**: every 4–6 hours.
- **Company list**: maintained in a version-controlled config file you can extend.

---

## 1. Requirements — clarified and challenged

**Functional**
- Maintain a list of companies (name + careers URL/identifier) in a file you edit.
- On a schedule, fetch each company's current open roles.
- Filter to Sydney-relevant roles (see location handling below — several sites
  only filter by country, not city).
- Match job titles against a keyword list (OR-match: any keyword hit = match).
- Track which jobs have already been seen, so you're only notified about **new**
  postings, not the same job every run.
- Email a digest of new matches.

**Non-functional (this is where I pushed back on "enterprise" instincts)**
- **Reliability over completeness**: better to reliably check 10 sites than to
  build a generic scraper that "should" work on any site and silently breaks.
- **A broken connector must be loud, never silent.** This is the single most
  important non-functional requirement you named (point 6), so it shapes the
  architecture directly — see §6.
- **No servers, no queues, no containers.** This is a single scheduled script on
  your own Mac. Anything that smells like infrastructure (message queues, a web
  UI, a database server) is unnecessary complexity for a 10–20 company personal
  tool and has been deliberately left out.
- **Cheap to extend**: adding company #11 should usually mean adding ~5 lines to
  a config file, not writing new code — true for 7 of your 10 initial companies
  (see §2).

---

## 2. Site investigation — how each of the 10 actually exposes jobs

I fetched every URL you gave me directly (curl for static inspection, then a
real browser with network-request inspection for the JS-heavy ones) and traced
each back to its actual data source rather than assuming. Findings:

| # | Company | Real data source | Tier |
|---|---|---|---|
| 1 | **Block** | Greenhouse public API, board token `block`: `boards-api.greenhouse.io/v1/boards/block/jobs?content=true`. Clean JSON, `location.name` field (e.g. "Sydney, Australia"). | **1 — API** |
| 2 | **Deputy** | Lever public API, slug `deputy`: `api.lever.co/v0/postings/deputy?mode=json`. Confirms your note — `categories.location` is sometimes just "Australia", not "Sydney". | **1 — API** |
| 3 | **Dovetail** | Ashby public API, board `dovetail`: `api.ashbyhq.com/posting-api/job-board/dovetail`. `location` field gives city directly (e.g. "Sydney"). | **1 — API** |
| 4 | **SafetyCulture (Mitti)** | Ashby public API, board `safetyculture`: `api.ashbyhq.com/posting-api/job-board/safetyculture`. Same clean shape as Dovetail. | **1 — API** |
| 5 | **Rokt** | Workable public widget API, numeric account `157387`: `apply.workable.com/api/v1/widget/accounts/157387`. Despite the site's UI only showing country, the raw API returns full `city`/`state`/`country` per job — the "expanding sections, no URL change" behaviour you noticed is purely a UI quirk we bypass entirely. | **1 — API** |
| 6 | **Atlassian** | Undocumented but simple first-party JSON endpoint: `www.atlassian.com/endpoint/careers/listings`. Returns **all** roles worldwide as one JSON array (title, `locations[]`, category, full description) — the site does its Australia/team filtering client-side in JS, so we replicate that filtering ourselves after fetching. | **1 — API** |
| 7 | **Employment Hero** | Their own in-house ATS product, embedded via a widget that calls `ats-cdn.ehrocks.com/ats/api/v1/embedded/widget` using an org id (`data-org-id` found in the embed script: `3cfd1633-4920-488d-be7e-985df4acfd1b`). I found the endpoint and the org id but didn't get a live successful call in the time I spent (widget loads lazily/async and didn't fire in my short session) — needs one confirmation spike (~30 min) in Phase 1, not a blocker to the design. | **1 — API (pending confirmation)** |
| 8 | **Wise** | Attrax (white-labelled careers-site platform), fully server-rendered HTML. Each job card carries a ready-made city class, e.g. `attrax-vacancy-tile--sydney` — no JS execution needed, just fetch + parse. | **2 — HTML scrape** |
| 9 | **Airwallex** | WordPress + Elementor Pro "Loop Grid" with a custom `location` taxonomy. Initial HTML response (with `?location[]=sydney` in the query string) already contains the filtered job cards server-rendered — no documented REST endpoint, but no JS execution needed either. | **2 — HTML scrape** |
| 10 | **Canva** | Custom Umbraco-based board with a real API (`lifeatcanva.com/umbraco/jobboard/CandidateJobs/GetRecentJobs`) — but the entire domain sits behind **Cloudflare's JS bot-challenge**, which blocks plain HTTP requests (confirmed: curl gets a "Just a moment…" challenge page). A real browser passes it fine. Filters by country only; city is in the per-listing text (e.g. "Sydney, NSW, Australia"). | **3 — needs headless browser** |

**Why this matters for the architecture**: 7 of 10 companies reduce to "call a
documented (or simple first-party) JSON API and read a field" — this is the
cheap, boring, reliable path and it's most of your list. Only Canva needs the
heavy tool (a real browser). This directly informs §3 and §7.

---

## 3. Proposed architecture

A single Python project, run on a schedule, no servers:

```
jobs-monitor/
  companies.yml          # the file you maintain — name, connector type, connector config
  keywords.yml           # your keyword list
  jobsmonitor/
    connectors/
      base.py            # Job dataclass + Connector protocol
      greenhouse.py       # generic — config: board token
      lever.py             # generic — config: company slug
      ashby.py             # generic — config: board name
      workable.py          # generic — config: account id
      atlassian.py         # one-off first-party JSON connector
      employmenthero.py    # one-off first-party JSON connector
      attrax_html.py        # generic HTML-scrape — config: base URL, CSS selectors
      elementor_html.py     # one-off HTML-scrape for Airwallex
      canva_browser.py      # one-off, Playwright-based
    matcher.py             # keyword + Sydney/Australia location filtering
    store.py               # SQLite: seen-jobs table + run-history table
    notifier.py            # builds & sends the email digest
    runner.py              # orchestrates: for each company -> fetch -> match -> diff -> notify
  tests/
    fixtures/              # saved real responses (captured today) per connector
    test_connectors.py
    test_matcher.py
  run.py                   # entrypoint launchd calls
```

**Why connectors, not one generic scraper**: 4 of your 10 companies (Greenhouse,
Lever, Ashby, Workable) sit on the *same* well-known ATS platforms. A generic
`GreenhouseConnector(board_token)` etc. means adding a future Greenhouse-hosted
company is a one-line config addition, not new code — this is what makes the
system "cheap to extend" per your requirement. HTML-scrape and browser
connectors are one-off per site by necessity (their markup isn't shared), but
they're isolated behind the same `Connector` interface so the rest of the
pipeline (matching, dedup, notification, observability) doesn't care which tier
a company is in.

**`companies.yml` sketch** (illustrative, not final):
```yaml
- name: Block
  connector: greenhouse
  config: { board_token: block }
- name: Deputy
  connector: lever
  config: { slug: deputy }
- name: Dovetail
  connector: ashby
  config: { board: dovetail }
- name: Rokt
  connector: workable
  config: { account_id: "157387" }
- name: Canva
  connector: canva_browser
  config: { url: "https://www.lifeatcanva.com/en/jobs/" }
```

---

## 4. Deterministic vs LLM judgement

Per your note (a), **v1 is 100% deterministic — no LLM anywhere in the pipeline**:
- Fetching: plain HTTP (or headless-browser render for Canva only) — deterministic.
- Location filtering: exact/substring match against a location field returned by
  the API/HTML (e.g. `"Sydney" in location_text`). For companies that only
  expose country-level location (Deputy, and possibly others), don't silently
  drop them — tag as `location_confidence: country_only` and include them in the
  digest clearly marked, so you see them rather than lose them.
- Keyword matching: your keyword list is a list of **full phrases**, not single
  words (e.g. `"Program Manager"`, `"Site Reliability"`). A title matches if it
  **contains the entire phrase** as a case-insensitive substring. Phrases are
  never split into individual words for matching, so `"Program Manager"` will
  match "Senior Program Manager, Platform" but will **not** match "Engineering
  Manager" or "Program Lead" — no accidental single-word matches like the
  generic word "Manager" pulling in unrelated titles. Any phrase hit anywhere in
  the list is enough to flag the job (OR across phrases, exact-substring per
  phrase).
- Dedup: exact job-ID match against SQLite.

**Where an LLM could add value later (explicitly out of scope for v1)**:
- Semantic title matching beyond literal keywords (e.g. "Platform Engineer"
  matching a "Senior Infra SRE" keyword intent) — genuinely useful but is a
  precision/recall trade-off you didn't ask for yet.
- Summarizing/ranking the digest email when match volume grows.
- Extracting structured location from messy free-text on some future company
  whose careers page doesn't expose a clean field.

None of these are needed for 10 companies with a fixed keyword list — adding an
LLM now would be complexity the requirements don't call for.

---

## 5. Storage, scheduling, notification

**Storage**: SQLite (Python's built-in `sqlite3`, no server, one file:
`jobsmonitor.db`). Two tables:
- `seen_jobs (company, job_id, title, url, location, first_seen_at)` — dedup source.
- `run_history (company, run_at, status, jobs_fetched, new_matches, error)` — this
  table is what makes a silent failure impossible (see §6).

SQLite over a flat JSON file because run-history + dedup both benefit from
simple queries (e.g. "show me last 5 runs for Wise") and SQLite costs nothing
extra to set up — it's still a single file, still zero infrastructure.

**Scheduling**: `launchd`, not `cron`. On macOS, `launchd` is the supported
mechanism and (via `StartInterval`) will catch up a missed run after the Mac
wakes from sleep, which plain `cron` handles poorly. A `LaunchAgent` plist runs
`run.py` every 4–6 hours.

**Notification**: email via Gmail SMTP with an app password (no new third-party
account needed since you already have the Gmail address) — sent to
gilesbdavis@gmail.com. Two distinct email types, which matters for §6:
1. **New matches digest** — normal case, only sent when there's something to report.
2. **Connector degraded alert** — sent when a connector fails or looks broken
   (see below), always sent even if it means an "empty" run — this is what
   prevents a failure from looking like "no new jobs."

---

## 6. Testing & observability — making failure loud

This was your explicit concern, so it's a first-class part of the design, not
an afterthought:

- **Every run writes to `run_history`**, per company, with an explicit `status`
  (`ok` / `error` / `degraded`), not just a job count. "Zero new matches" and
  "the connector threw an exception" must never look the same.
- **Degraded-state heuristic**: if a connector returns 0 total jobs (not just 0
  new matches) when its last successful run returned >0, or if the HTTP
  request fails, times out, or returns a non-200, mark that run `degraded`/`error`.
- **A degraded/error run always triggers the alert email**, separate from the
  normal digest, so a broken scraper surfaces immediately rather than quietly
  producing empty digests forever.
- **Structure-check tests for the two HTML-scrape connectors** (Wise, Airwallex):
  since these depend on the site's markup rather than a stable API, each has a
  test asserting its CSS selectors still match >0 known elements against a live
  fetch — the fixture most likely to silently rot over time.
- **Fixture-based unit tests** for every connector, using real responses
  captured during this investigation (I already have working saved copies of
  the Greenhouse/Lever/Ashby/Workable/Atlassian responses in
  `/private/tmp/.../scratchpad/` from today's research — these become the first
  test fixtures, so parsing logic is tested without hitting the network on
  every CI/local run).
- **Retry with backoff** (e.g. 2 retries, short delay) for transient network
  errors before a run is declared `error` — avoids false alarms from one flaky
  request.
- **Local log file** (rotating, plain text) for day-to-day debugging — no
  Grafana/Prometheus/hosted logging. A `python run.py --status` command that
  prints the last N runs per company from `run_history` is the whole
  "dashboard" this tool needs.

---

## 7. Incremental implementation plan & estimate

Phases are ordered so you get a working, reliably-notifying tool on the 7
API-backed companies first, then layer on the harder two tiers — this is the
"small v1" cut: **v1 ships without Canva** (or with Canva stubbed/manual) if
time is tight, since it's the one company needing a heavyweight dependency
(Playwright + browser binaries) for 1/10 of the value. You can add it as a
fast-follow once the core is proven.

| Phase | Work | Est. hours |
|---|---|---|
| 0 | Repo setup: `git init`, GitHub repo (private, recommend), Python project scaffold, `.gitignore` for secrets, README | 0.5–1 |
| 1 | Core data model (`Job`), SQLite schema, dedup logic | 1 |
| 2 | Connector framework + the 6 confirmed Tier-1 API connectors (Greenhouse, Lever ×1, Ashby ×2, Workable, Atlassian) — endpoints, auth, and field shapes are already known from today's research, so this is mostly writing the shared base class once and then plugging in config per company | 2.5–3 |
| 2b | Employment Hero connector, once the endpoint is confirmed live | 0.5 |
| 3 | HTML-scrape connectors: Wise (Attrax), Airwallex (Elementor) + structure-check tests — the slowest-per-item work since each needs real CSS selectors against real markup | 1.5–2 |
| 4 | Keyword + location matcher — exact-phrase substring match (not word-level), incl. "country-only" flagging edge case | 0.5 |
| 5 | Email notifier (digest + degraded-alert), SMTP setup | 1 |
| 6 | `launchd` scheduling, run history, `--status` command | 1 |
| 7 | Fixture-based tests using the real responses already captured today + a full dry-run against live sites | 1.5–2 |
| 8 | (Fast-follow, optional for v1) Canva connector via Playwright | 2–3 |

**Total for v1 (Phases 0–7): roughly 9–12 hours.** Add **2–3 hours** if Canva is
included in the initial cut rather than deferred.

This is meaningfully less than a typical scraping-integration project because
the usual time sink — reverse-engineering each site's undocumented API — is
already done (§2). What's left is boilerplate CRUD-shaped work (HTTP call →
parse → SQLite → email) with no UI and no deployment target, which is exactly
where Claude Code pairing is fastest: you review a pattern once, then approve
five near-identical connector diffs quickly rather than steering five separate
designs.

---

## Decisions confirmed

1. **Canva**: fast-follow (Phase 8), not part of the initial v1 cut.
2. **Python packaging**: plain venv + `requirements.txt`.
3. **GitHub repo**: private.
4. **Keyword matching**: full-phrase, case-insensitive substring match (see §4)
   — not single-word/tokenized matching.
