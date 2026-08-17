#!/usr/bin/env python3
import argparse
import logging
import logging.handlers
import sys
from pathlib import Path

from dotenv import load_dotenv

from jobsmonitor.config import load_companies, load_company_homepages, load_keywords
from jobsmonitor.notifier import EmailConfig
from jobsmonitor.runner import run
from jobsmonitor.sheets import SheetConfig, SheetLogger
from jobsmonitor.store import Store

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "jobsmonitor.db"
LOG_PATH = BASE_DIR / "jobsmonitor.log"
COMPANIES_PATH = BASE_DIR / "companies.yml"
KEYWORDS_PATH = BASE_DIR / "keywords.yml"


def setup_logging() -> None:
    handler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])


def print_status(store: Store, limit: int = 20) -> None:
    rows = store.recent_runs(limit=limit)
    if not rows:
        print("No runs recorded yet.")
        return
    for r in rows:
        fetched = r["jobs_fetched"] if r["jobs_fetched"] is not None else "-"
        print(
            f"{r['run_at']}  {r['company']:<20} {r['status']:<9} "
            f"fetched={fetched:<5} new={r['new_matches']:<3} {r['error'] or ''}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sydney tech jobs monitor")
    parser.add_argument("--status", action="store_true", help="print recent run history and exit")
    args = parser.parse_args()

    load_dotenv(BASE_DIR / ".env")

    store = Store(DB_PATH)
    try:
        if args.status:
            print_status(store)
            return 0

        setup_logging()
        connectors = load_companies(COMPANIES_PATH)
        keywords = load_keywords(KEYWORDS_PATH)
        homepages = load_company_homepages(COMPANIES_PATH)
        email_config = EmailConfig.from_env()

        sheet_config = SheetConfig.from_env()
        sheet_logger = SheetLogger(sheet_config) if sheet_config else None

        run(store, connectors, keywords, email_config, sheet_logger, homepages)
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
