import pytest

from jobsmonitor.connectors.base import ConnectorError
from jobsmonitor.connectors.canva import CanvaConnector
from jobsmonitor.models import Job


@pytest.fixture
def connector():
    return CanvaConnector(company="Canva", base_url="https://www.lifeatcanva.com")


def test_parse_total_from_text(connector):
    text = "1 to 20 of 123 Live Results\n\nSenior Frontend Engineer..."
    assert connector.parse_total_from_text(text) == 123


def test_parse_total_from_text_raises_when_pattern_missing(connector):
    with pytest.raises(ConnectorError):
        connector.parse_total_from_text("Something went wrong")


def test_build_job_makes_relative_url_absolute(connector):
    job = connector.build_job(
        job_id="6000000001316467",
        title="Senior Frontend Engineer",
        href="/en/jobs/6000000001316467/senior-frontend-engineer/",
        location_text="Sydney, NSW, Australia\nEngineering",
    )
    assert job.url == "https://www.lifeatcanva.com/en/jobs/6000000001316467/senior-frontend-engineer/"
    assert job.location == "Sydney, NSW, Australia, Engineering"
    assert job.job_id == "6000000001316467"


def test_build_job_falls_back_to_url_when_no_job_id(connector):
    job = connector.build_job(
        job_id=None,
        title="Some Role",
        href="/en/jobs/x/some-role/",
        location_text="Sydney, Australia",
    )
    assert job.job_id == job.url


def test_validate_australia_filter_applied_passes_when_mostly_australian(connector):
    # 9/10 mention Australia (above the 0.9 threshold) — one secondary/remote
    # location without the word "Australia" shouldn't trip the guard on its own
    jobs = [Job("Canva", str(i), "A", f"https://x/{i}", "Sydney, NSW, Australia") for i in range(9)]
    jobs.append(Job("Canva", "9", "B", "https://x/9", "Remote - Remote"))
    connector.validate_australia_filter_applied(jobs)  # should not raise


def test_validate_australia_filter_applied_raises_on_degraded_unfiltered_response(connector):
    # the exact failure mode observed during development: country filter
    # silently ignored, worldwide unfiltered list returned instead
    jobs = [
        Job("Canva", "1", "A", "https://x/1", "Texas, KY, United States"),
        Job("Canva", "2", "B", "https://x/2", "San Francisco, , United States"),
        Job("Canva", "3", "C", "https://x/3", "Prague, Prague, Czechia"),
        Job("Canva", "4", "D", "https://x/4", "Sydney, NSW, Australia"),
    ]
    with pytest.raises(ConnectorError, match="country filter does not appear to have applied"):
        connector.validate_australia_filter_applied(jobs)


def test_validate_australia_filter_applied_noop_on_empty_list(connector):
    connector.validate_australia_filter_applied([])  # should not raise
