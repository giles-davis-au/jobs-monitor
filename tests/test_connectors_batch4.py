import httpx
import pytest

from jobsmonitor.connectors.base import ConnectorError
from jobsmonitor.connectors.builtin import BuiltInConnector
from tests.conftest import load_text_fixture


def test_builtin_parses_fixture(mock_get):
    html = load_text_fixture("builtin_airtasker.html")
    mock_get.returns(httpx.Response(200, text=html))

    jobs = BuiltInConnector("Airtasker", "https://builtinsydney.au", "194323").fetch()

    assert len(jobs) == 2
    assert all(j.location == "Sydney" for j in jobs)
    assert all(j.url.startswith("https://builtinsydney.au/job/") for j in jobs)
    assert jobs[0].title == "Product Marketing Specialist"
    assert jobs[0].job_id == "10678522"


def test_builtin_raises_when_no_cards_found(mock_get):
    mock_get.returns(httpx.Response(200, text="<html><body>no cards here</body></html>"))
    with pytest.raises(ConnectorError):
        BuiltInConnector("Airtasker", "https://builtinsydney.au", "194323").fetch()
