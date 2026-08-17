import httpx
import pytest

from jobsmonitor.connectors.bamboohr import BambooHrConnector
from jobsmonitor.connectors.base import ConnectorError
from jobsmonitor.connectors.revolut import RevolutConnector
from tests.conftest import load_json_fixture


def test_bamboohr_parses_fixture(mock_get):
    fixture = load_json_fixture("bamboohr_zepto.json")
    mock_get.returns(httpx.Response(200, json=fixture))

    jobs = BambooHrConnector("Zepto", "zepto").fetch()

    assert len(jobs) == 3
    assert all(j.url.startswith("https://zepto.bamboohr.com/careers/") for j in jobs)
    sydney_job = next(j for j in jobs if j.job_id == "99")
    assert sydney_job.location == "Sydney, New South Wales, Australia"
    # atsLocation present but all fields null -> empty string, not "None"
    no_city_job = next(j for j in jobs if j.job_id == "101")
    assert no_city_job.location == "Australia"


def test_bamboohr_raises_on_unexpected_shape(mock_get):
    mock_get.returns(httpx.Response(200, json={"nope": "wrong shape"}))
    with pytest.raises(ConnectorError):
        BambooHrConnector("Zepto", "zepto").fetch()


def test_revolut_parse_position_extracts_locations():
    connector = RevolutConnector()
    fixture = load_json_fixture("revolut_positions.json")

    jobs = [connector._parse_position(p) for p in fixture]

    assert len(jobs) == 2
    sydney_job = jobs[0]
    assert sydney_job.title == "Finance & Strategy Manager"
    assert sydney_job.location == "Sydney; London"
    assert sydney_job.url == (
        "https://www.revolut.com/en-AU/careers/position/"
        "finance-strategy-manager-a2001837-cd87-4217-a09f-68d8d9c9ea6e/"
    )


def test_revolut_slugify_strips_non_alphanumerics():
    connector = RevolutConnector()

    assert connector._slugify("Finance & Strategy Manager") == "finance-strategy-manager"
    assert connector._slugify("Graphic Designer (Growth)") == "graphic-designer-growth"


def test_revolut_parse_position_handles_missing_locations():
    connector = RevolutConnector()

    job = connector._parse_position({"id": "abc", "text": "Some Role", "locations": None})

    assert job.location == ""
