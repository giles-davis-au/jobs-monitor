from unittest.mock import patch

import httpx

from jobsmonitor.models import Job, LocationConfidence
from jobsmonitor.notifier import EmailConfig, send_digest

CONFIG = EmailConfig(api_key="x", from_addr="from@x.com", to_addr="to@x.com")


def _mock_resend_response():
    return httpx.Response(
        200, json={"id": "abc"}, request=httpx.Request("POST", "https://api.resend.com/emails")
    )


def test_send_digest_with_zero_matches_still_sends_a_heartbeat_email():
    with patch("httpx.post") as mock_post:
        mock_post.return_value = _mock_resend_response()
        send_digest(CONFIG, [], ["Program Manager", "Delivery Manager"])

    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert payload["subject"] == "[jobs-monitor] 0 new matches"
    assert "Searching for: Program Manager, Delivery Manager" in payload["text"]
    assert "No new matches this run." in payload["text"]


def test_send_digest_with_matches_lists_them_and_counts_in_subject():
    job = Job("Block", "1", "Program Manager", "https://block.xyz/careers/jobs/1", "Sydney, Australia")

    with patch("httpx.post") as mock_post:
        mock_post.return_value = _mock_resend_response()
        send_digest(CONFIG, [(job, LocationConfidence.CITY)], ["Program Manager"])

    payload = mock_post.call_args.kwargs["json"]
    assert payload["subject"] == "[jobs-monitor] 1 new match(es)"
    assert "Program Manager (Block)" in payload["text"]
    assert "No new matches" not in payload["text"]


def test_send_digest_flags_country_only_location_confidence():
    job = Job("Deputy", "1", "Program Manager", "https://x/1", "Australia")

    with patch("httpx.post") as mock_post:
        mock_post.return_value = _mock_resend_response()
        send_digest(CONFIG, [(job, LocationConfidence.COUNTRY_ONLY)], ["Program Manager"])

    payload = mock_post.call_args.kwargs["json"]
    assert "verify city" in payload["text"]
