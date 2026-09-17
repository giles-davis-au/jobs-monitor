# jobs-monitor

Personal tool that watches a configurable list of tech company careers pages,
detects newly-posted Sydney-relevant roles, and emails a digest of titles
matching a keyword list.

See [`docs/PLAN.md`](docs/PLAN.md) for the full design (architecture, per-site
connector research, testing/observability approach, and implementation phases).

The build process: this was built iteratively with Claude Code as a pairing
tool, commit by commit, over many sessions. I made the architecture,
prioritization, and scope calls and reviewed and directed the changes. The
commit history is a record of that process, including real bugs found and
fixed along the way.

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

Runs on macOS via `launchd`, installed as a **LaunchDaemon** (system domain,
`/Library/LaunchDaemons`), every 3 hours counted from whenever the job is
(re)installed — not anchored to fixed clock times — plus once immediately at
install, via `RunAtLoad`. Nothing is installed automatically; the three
sections below are the full lifecycle.

It's a LaunchDaemon rather than a LaunchAgent deliberately — see
**Troubleshooting** below for why. All commands need `sudo`, and will prompt
for your Mac password.

### Install and run

First, edit `launchd/com.gilesdavis.jobsmonitor.plist` and replace every
`/path/to/jobs-monitor` placeholder with this project's actual absolute path
on your machine — launchd requires absolute paths, so `~` and relative paths
won't work. Then:

```bash
cd /path/to/jobs-monitor
sudo cp launchd/com.gilesdavis.jobsmonitor.plist /Library/LaunchDaemons/
sudo chown root:wheel /Library/LaunchDaemons/com.gilesdavis.jobsmonitor.plist
sudo chmod 644 /Library/LaunchDaemons/com.gilesdavis.jobsmonitor.plist
sudo launchctl bootstrap system /Library/LaunchDaemons/com.gilesdavis.jobsmonitor.plist
```

The `cd` matters — the `cp` command uses a path relative to the project
folder. The plist has a `UserName` key set to `gilesdavis`, so the daemon
runs as you (not root) — file permissions and `.env` access behave exactly
like a normal user process. Once installed, it fires immediately
(`RunAtLoad`), then every 3 hours after that, indefinitely, with no Claude
Code session and no login session needed at all.

### Check status

```bash
.venv/bin/python run.py --status                                 # per-company run history — the useful one
launchctl print system/com.gilesdavis.jobsmonitor | head -20     # confirms launchd itself has it registered (no sudo needed to read)
```

Logs: day-to-day run logging goes to `jobsmonitor.log`; launchd's own
stdout/stderr for the process go to `launchd/stdout.log` and
`launchd/stderr.log` (catches startup failures before app logging even kicks
in, e.g. a Python crash on import).

### Troubleshooting: why a LaunchDaemon, not a LaunchAgent

This ran as a LaunchAgent (`gui/$(id -u)` domain) originally. On 2026-08-17 a
scheduled 3-hour run silently never happened: the system log showed launchd
firing the timer exactly on schedule (`pending spawn, domain in
on-demand-only mode: com.gilesdavis.jobsmonitor`) but never actually
dispatching it — no new log lines, no email, nothing — while the Mac stayed
awake the whole time (no sleep/wake events logged). The GUI (`gui/<uid>`)
launchd domain can defer a background agent's spawn until it decides the
login session is genuinely "active" (unlocked/interacted-with), not just
powered on — a real limitation for a script that's supposed to run
unattended. `sfltool dumpbtm` confirmed this wasn't a Background Task
Management permission issue (the item was `[enabled, allowed, notified]`) —
it was specifically GUI-session-activity gating.

A LaunchDaemon runs in the system domain, which isn't tied to any login
session at all, so it isn't subject to this gating — the fix is structural,
not a retry/workaround. If a run is ever missed, force it manually:

```bash
sudo launchctl kickstart -p system/com.gilesdavis.jobsmonitor
```

That run becomes the new baseline for the 3-hour schedule (next automatic
run is 3 hours after it, not after the original install time).

### Stop it

```bash
sudo launchctl bootout system/com.gilesdavis.jobsmonitor
sudo rm /Library/LaunchDaemons/com.gilesdavis.jobsmonitor.plist
```

This only stops the schedule — `run.py` still works as a one-off afterwards
(`.venv/bin/python run.py`), and reinstalling later is just the Install
section again.
