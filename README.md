# jobs-monitor

Personal tool that watches a configurable list of tech company careers pages,
detects newly-posted Sydney-relevant roles, and emails a digest of titles
matching a keyword list.

See [`docs/PLAN.md`](docs/PLAN.md) for the full design (architecture, per-site
connector research, testing/observability approach, and implementation phases).

## Setup

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium   # needed for the Canva connector
```

## Configuration

- `companies.yml` — the list of companies to monitor and how to fetch each one.
- `keywords.yml` — your list of match phrases (full-phrase substring match
  against job titles, case-insensitive).
- Email is sent via [Resend](https://resend.com)'s API — sign up (free tier),
  create an API key, and set it in `.env` (see `.env.example`, never
  committed to git).
- Canva is the one connector that needs a real browser (Cloudflare-protected
  site) — see `jobsmonitor/connectors/canva.py` for details, including a
  known risk: it works correctly from a trusted/residential IP (your Mac)
  but has been observed silently returning unfiltered worldwide results
  instead of Australia-only ones when run from a lower-trust automated
  environment (e.g. a cloud CI IP). The connector validates this and raises
  rather than trusting bad data, but this means Canva may not work reliably
  if this tool is ever migrated to run from GitHub Actions or similar.

### Google Sheet logging (optional)

New matches are also appended to a Google Sheet if configured — a row per
match with columns `# | Date Retrieved | Company | Job Title`, both Company
and Job Title hyperlinked. This is off by default (nothing breaks without
it).

Deliberately **not** implemented via a Google Cloud service account —
that requires a Cloud project + IAM setup for what's really just "let my
own script write to my own sheet." Instead this uses a small
**Apps Script Web App bound directly to the sheet**: no Google Cloud
Console, no service account, no credential file to protect, just a URL +
shared secret. One-time setup, entirely inside Google Sheets:

1. Open your target sheet → **Extensions → Apps Script**.
2. Delete the placeholder code and paste in the contents of
   [`apps-script/Code.gs`](apps-script/Code.gs) from this repo.
3. Replace `REPLACE_WITH_YOUR_OWN_SECRET` with a random string (e.g. run
   `python3 -c "import secrets; print(secrets.token_hex(24))"`) — keep a
   copy, it goes in `.env` too. `TARGET_GID` is already set to your sheet's
   tab.
4. **Deploy → New deployment** → click the gear icon next to "Select type" →
   **Web app**.
   - Execute as: **Me**
   - Who has access: **Anyone** (this doesn't mean "publicly discoverable" —
     the URL is an unguessable long ID, and the shared secret is checked
     inside the script on every request; same trust model as any other
     bearer-token webhook, e.g. the Resend API key)
5. Click **Deploy**. The first time, Google shows an "unverified app"
   warning — that's normal for a personal script authorizing itself to
   edit your own sheet, not a real red flag; click **Advanced → Go to
   (project name)** to proceed.
6. Copy the **Web app URL** it gives you (`https://script.google.com/macros/s/.../exec`).
7. In `.env`, set `GOOGLE_SHEETS_WEBHOOK_URL` to that URL and
   `GOOGLE_SHEETS_WEBHOOK_SECRET` to the secret from step 3.

The sheet needs its header row (`# | Date Retrieved | Company | Job Title`)
already in place — the tool only ever appends after existing rows, it never
touches row 1.

## Running

```bash
.venv/bin/python run.py   # one fetch-and-notify cycle, run manually
```

For unattended ongoing runs (no Claude Code needed) see **Scheduling** below,
which also covers checking status and stopping it.

## Scheduling

Runs on macOS via `launchd` every 3 hours, counted from whenever the job is
(re)installed — not anchored to fixed clock times — plus once immediately at
install, via `RunAtLoad`. Nothing is installed automatically; the three
sections below are the full lifecycle.

### Install and run

```bash
cd /Users/gilesdavis/Documents/Davis/coding/projects/jobs-monitor
cp launchd/com.gilesdavis.jobsmonitor.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.gilesdavis.jobsmonitor.plist
```

The `cd` matters — the `cp` command uses a path relative to the project
folder. Once installed, it fires immediately (`RunAtLoad`), then every 3
hours after that, indefinitely, with no Claude Code session needed.

### Check status

```bash
.venv/bin/python run.py --status                              # per-company run history — the useful one
launchctl print gui/$(id -u)/com.gilesdavis.jobsmonitor | head -20   # confirms launchd itself has it registered
```

Logs: day-to-day run logging goes to `jobsmonitor.log`; launchd's own
stdout/stderr for the process go to `launchd/stdout.log` and
`launchd/stderr.log` (catches startup failures before app logging even kicks
in, e.g. a Python crash on import).

### Stop it

```bash
launchctl bootout gui/$(id -u)/com.gilesdavis.jobsmonitor
rm ~/Library/LaunchAgents/com.gilesdavis.jobsmonitor.plist
```

This only stops the schedule — `run.py` still works as a one-off afterwards
(`.venv/bin/python run.py`), and reinstalling later is just the Install
section again.
