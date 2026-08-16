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

## Running

```bash
.venv/bin/python run.py            # one fetch-and-notify cycle
.venv/bin/python run.py --status   # print recent run history per company
```

## Scheduling

Runs on macOS via `launchd` every 5 hours (within the agreed 4-6h window).
`launchd/com.gilesdavis.jobsmonitor.plist` is ready to install — nothing is
installed automatically, run this yourself when you're ready:

```bash
cp launchd/com.gilesdavis.jobsmonitor.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.gilesdavis.jobsmonitor.plist
```

Check it's loaded:

```bash
launchctl print gui/$(id -u)/com.gilesdavis.jobsmonitor | head -20
```

To stop/uninstall:

```bash
launchctl bootout gui/$(id -u)/com.gilesdavis.jobsmonitor
rm ~/Library/LaunchAgents/com.gilesdavis.jobsmonitor.plist
```

launchd's own stdout/stderr for the process go to `launchd/stdout.log` and
`launchd/stderr.log` (catches startup failures before app logging kicks in);
day-to-day run logging goes to `jobsmonitor.log`.
