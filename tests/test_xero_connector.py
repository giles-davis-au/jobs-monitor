import pytest

from jobsmonitor.connectors.base import ConnectorError
from jobsmonitor.connectors.xero import XeroConnector
from jobsmonitor.models import Job


@pytest.fixture
def connector():
    return XeroConnector(company="Xero", base_url="https://careers.xero.com")


def test_parse_total_from_text(connector):
    text = "Displaying 1 to 20 of 44 matching jobs\n\nSales Development Specialist..."
    assert connector.parse_total_from_text(text) == 44


def test_parse_total_from_text_raises_when_pattern_missing(connector):
    with pytest.raises(ConnectorError):
        connector.parse_total_from_text("Something went wrong")


def test_build_job_makes_relative_url_absolute(connector):
    job = connector.build_job(
        job_id="e0f5c546-dd6a-4db3-a631-952dfd8c6c67",
        title="Sales Development Specialist",
        href="/jobs/e0f5c546-dd6a-4db3-a631-952dfd8c6c67/sales-development-specialist/",
        location_text="Sydney, New South Wales, Australia\nRevenue",
    )
    assert job.url == (
        "https://careers.xero.com/jobs/e0f5c546-dd6a-4db3-a631-952dfd8c6c67/sales-development-specialist/"
    )
    assert job.location == "Sydney, New South Wales, Australia, Revenue"
    assert job.job_id == "e0f5c546-dd6a-4db3-a631-952dfd8c6c67"


def test_build_job_falls_back_to_url_when_no_job_id(connector):
    job = connector.build_job(
        job_id=None,
        title="Some Role",
        href="/jobs/x/some-role/",
        location_text="Sydney, Australia",
    )
    assert job.job_id == job.url


def test_validate_australia_filter_applied_passes_when_mostly_australian(connector):
    jobs = [Job("Xero", str(i), "A", f"https://x/{i}", "Sydney, NSW, Australia") for i in range(9)]
    jobs.append(Job("Xero", "9", "B", "https://x/9", "Remote - Remote"))
    connector.validate_australia_filter_applied(jobs)  # should not raise


def test_validate_australia_filter_applied_raises_on_degraded_unfiltered_response(connector):
    jobs = [
        Job("Xero", "1", "A", "https://x/1", "Hawthorn, Victoria, Australia"),
        Job("Xero", "2", "B", "https://x/2", "San Francisco, CA, United States"),
        Job("Xero", "3", "C", "https://x/3", "London, United Kingdom"),
        Job("Xero", "4", "D", "https://x/4", "Singapore"),
    ]
    with pytest.raises(ConnectorError, match="country filter does not appear to have applied"):
        connector.validate_australia_filter_applied(jobs)


def test_validate_australia_filter_applied_noop_on_empty_list(connector):
    connector.validate_australia_filter_applied([])  # should not raise
