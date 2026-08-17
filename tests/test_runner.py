from unittest.mock import MagicMock, patch

from jobsmonitor.connectors.base import ConnectorError
from jobsmonitor.models import Job
from jobsmonitor.notifier import EmailConfig
from jobsmonitor.runner import run
from jobsmonitor.store import Store

CONFIG = EmailConfig(api_key="x", from_addr="x", to_addr="x")


class FakeConnector:
    def __init__(self, company, jobs=None, error=None):
        self.company = company
        self._jobs = jobs or []
        self._error = error

    def fetch(self):
        if self._error:
            raise ConnectorError(self._error)
        return self._jobs


def test_failed_connector_is_recorded_as_error_and_alerted_not_silently_empty(tmp_path):
    store = Store(tmp_path / "test.db")
    connectors = [FakeConnector("Broken Co", error="site returned 500")]

    with patch("jobsmonitor.runner.send_degraded_alert") as alert, patch(
        "jobsmonitor.runner.send_digest"
    ) as digest:
        run(store, connectors, keywords=["Program Manager"], email_config=CONFIG)

    # the failure must be loud: a distinct alert, and NOT folded into the digest
    alert.assert_called_once_with(CONFIG, "Broken Co", "error", "site returned 500")
    digest.assert_not_called()

    runs = store.recent_runs("Broken Co")
    assert runs[0]["status"] == "error"
    assert runs[0]["jobs_fetched"] is None  # distinct from "0 jobs found successfully"
    store.close()


def test_connector_returning_zero_after_previously_healthy_is_flagged_degraded(tmp_path):
    store = Store(tmp_path / "test.db")
    store.record_run("Flaky Co", status="ok", jobs_fetched=50, new_matches=0)

    connectors = [FakeConnector("Flaky Co", jobs=[])]  # now returns nothing

    with patch("jobsmonitor.runner.send_degraded_alert") as alert:
        run(store, connectors, keywords=["Program Manager"], email_config=CONFIG)

    alert.assert_called_once()
    assert store.recent_runs("Flaky Co")[0]["status"] == "degraded"
    store.close()


def test_connector_genuinely_having_zero_jobs_first_time_is_ok_not_degraded(tmp_path):
    store = Store(tmp_path / "test.db")
    connectors = [FakeConnector("New Co", jobs=[])]

    with patch("jobsmonitor.runner.send_degraded_alert") as alert:
        run(store, connectors, keywords=["Program Manager"], email_config=CONFIG)

    alert.assert_not_called()
    assert store.recent_runs("New Co")[0]["status"] == "ok"
    store.close()


def test_one_broken_connector_does_not_block_others_or_their_matches(tmp_path):
    store = Store(tmp_path / "test.db")
    healthy_job = Job("Healthy Co", "1", "Program Manager", "https://x/1", "Sydney, Australia")
    connectors = [
        FakeConnector("Broken Co", error="boom"),
        FakeConnector("Healthy Co", jobs=[healthy_job]),
    ]

    with patch("jobsmonitor.runner.send_degraded_alert"), patch(
        "jobsmonitor.runner.send_digest"
    ) as digest:
        run(store, connectors, keywords=["Program Manager"], email_config=CONFIG)

    assert store.recent_runs("Healthy Co")[0]["status"] == "ok"
    assert store.recent_runs("Healthy Co")[0]["new_matches"] == 1
    digest.assert_called_once()
    matched_jobs = digest.call_args[0][1]
    assert [job.job_id for job, _ in matched_jobs] == ["1"]
    store.close()


def test_dedup_prevents_renotifying_same_job_across_runs(tmp_path):
    store = Store(tmp_path / "test.db")
    job = Job("Co", "1", "Program Manager", "https://x/1", "Sydney, Australia")
    connectors = [FakeConnector("Co", jobs=[job])]

    with patch("jobsmonitor.runner.send_digest") as digest:
        run(store, connectors, keywords=["Program Manager"], email_config=CONFIG)
        run(store, connectors, keywords=["Program Manager"], email_config=CONFIG)

    assert digest.call_count == 1  # only the first run had a new match
    store.close()


def test_sheet_logger_receives_new_matches_and_homepages(tmp_path):
    store = Store(tmp_path / "test.db")
    job = Job("Block", "1", "Program Manager", "https://block.xyz/careers/jobs/1", "Sydney, Australia")
    connectors = [FakeConnector("Block", jobs=[job])]
    sheet_logger = MagicMock()
    homepages = {"Block": "https://block.xyz"}

    with patch("jobsmonitor.runner.send_digest"):
        run(
            store,
            connectors,
            keywords=["Program Manager"],
            email_config=CONFIG,
            sheet_logger=sheet_logger,
            homepages=homepages,
        )

    sheet_logger.append_matches.assert_called_once()
    matches_arg, homepages_arg = sheet_logger.append_matches.call_args[0]
    assert [job.job_id for job, _ in matches_arg] == ["1"]
    assert homepages_arg == homepages
    store.close()


def test_sheet_logger_failure_does_not_crash_the_run_or_block_email(tmp_path):
    store = Store(tmp_path / "test.db")
    job = Job("Block", "1", "Program Manager", "https://x/1", "Sydney, Australia")
    connectors = [FakeConnector("Block", jobs=[job])]
    sheet_logger = MagicMock()
    sheet_logger.append_matches.side_effect = RuntimeError("Google API is down")

    with patch("jobsmonitor.runner.send_digest") as digest:
        run(
            store,
            connectors,
            keywords=["Program Manager"],
            email_config=CONFIG,
            sheet_logger=sheet_logger,
        )

    digest.assert_called_once()  # email still sent despite sheet failure
    store.close()


def test_no_sheet_logger_is_fine(tmp_path):
    store = Store(tmp_path / "test.db")
    job = Job("Block", "1", "Program Manager", "https://x/1", "Sydney, Australia")
    connectors = [FakeConnector("Block", jobs=[job])]

    with patch("jobsmonitor.runner.send_digest"):
        run(store, connectors, keywords=["Program Manager"], email_config=CONFIG)  # sheet_logger=None default

    store.close()
