from unittest.mock import patch

import httpx

from jobsmonitor.models import Job, LocationConfidence
from jobsmonitor.sheets import SheetConfig, SheetLogger

CONFIG = SheetConfig(webhook_url="https://script.google.com/macros/s/abc/exec", secret="topsecret")


def test_append_matches_posts_expected_payload():
    job = Job("Block", "1", "Program Manager", "https://block.xyz/careers/jobs/1", "Sydney, Australia")
    logger = SheetLogger(CONFIG)

    with patch("httpx.post") as mock_post:
        mock_post.return_value = httpx.Response(
            200, json={"status": "ok", "appended": 1}, request=httpx.Request("POST", CONFIG.webhook_url)
        )
        logger.append_matches([(job, LocationConfidence.CITY)], {"Block": "https://block.xyz"})

    url, kwargs = mock_post.call_args[0][0], mock_post.call_args.kwargs
    assert url == CONFIG.webhook_url
    payload = kwargs["json"]
    assert payload["secret"] == "topsecret"
    assert len(payload["rows"]) == 1
    row = payload["rows"][0]
    assert row["companyName"] == "Block"
    assert row["companyUrl"] == "https://block.xyz"
    assert row["jobTitle"] == "Program Manager"
    assert row["jobUrl"] == "https://block.xyz/careers/jobs/1"
    import re

    assert re.match(r"\d{2}/\d{2}/\d{4}", row["dateRetrieved"])


def test_append_matches_falls_back_to_empty_company_url_when_no_homepage():
    job = Job("Unknown Co", "1", "Role", "https://x/1", "Sydney")
    logger = SheetLogger(CONFIG)

    with patch("httpx.post") as mock_post:
        mock_post.return_value = httpx.Response(
            200, json={"status": "ok", "appended": 1}, request=httpx.Request("POST", CONFIG.webhook_url)
        )
        logger.append_matches([(job, LocationConfidence.CITY)], {})

    row = mock_post.call_args.kwargs["json"]["rows"][0]
    assert row["companyUrl"] == ""


def test_append_matches_noop_on_empty_list():
    logger = SheetLogger(CONFIG)
    with patch("httpx.post") as mock_post:
        logger.append_matches([], {})
    mock_post.assert_not_called()


def test_append_matches_raises_when_webhook_reports_non_ok_status():
    job = Job("A", "1", "Role", "https://x/1", "Sydney")
    logger = SheetLogger(CONFIG)

    with patch("httpx.post") as mock_post:
        mock_post.return_value = httpx.Response(
            200, json={"status": "error", "message": "bad secret"},
            request=httpx.Request("POST", CONFIG.webhook_url),
        )
        try:
            logger.append_matches([(job, LocationConfidence.CITY)], {})
            raised = False
        except RuntimeError:
            raised = True
    assert raised


def test_sheet_config_from_env_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("GOOGLE_SHEETS_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("GOOGLE_SHEETS_WEBHOOK_SECRET", raising=False)
    assert SheetConfig.from_env() is None


def test_sheet_config_from_env_builds_config_when_set(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_WEBHOOK_URL", "https://script.google.com/macros/s/xyz/exec")
    monkeypatch.setenv("GOOGLE_SHEETS_WEBHOOK_SECRET", "s3cr3t")

    config = SheetConfig.from_env()

    assert config.webhook_url == "https://script.google.com/macros/s/xyz/exec"
    assert config.secret == "s3cr3t"
