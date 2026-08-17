import json
from pathlib import Path

import httpx
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_json_fixture(name: str):
    return json.loads((FIXTURES_DIR / name).read_text())


def load_text_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


@pytest.fixture
def mock_get(monkeypatch):
    """Patch httpx.Client.get to return canned responses in sequence.

    Usage: mock_get.returns(httpx.Response(200, json={...}))
           mock_get.returns(httpx.Response(200, text="<html>..."))
           mock_get.raises(httpx.ConnectError("boom"))
    """

    class MockGet:
        def __init__(self):
            self.queue = []
            self.calls = []

        def returns(self, response: httpx.Response):
            self.queue.append(("response", response))
            return self

        def raises(self, exc: Exception):
            self.queue.append(("raise", exc))
            return self

        def __call__(self, url, *args, **kwargs):
            self.calls.append(url)
            kind, value = self.queue.pop(0) if self.queue else ("raise", RuntimeError("no mock response queued"))
            if kind == "raise":
                raise value
            value.request = httpx.Request("GET", url)  # raise_for_status() requires this to be set
            return value

    mock = MockGet()
    monkeypatch.setattr(httpx.Client, "get", mock)
    return mock


@pytest.fixture
def mock_post(monkeypatch):
    """Same as `mock_get` but for httpx.Client.post (e.g. Workday's search API)."""

    class MockPost:
        def __init__(self):
            self.queue = []
            self.calls = []

        def returns(self, response: httpx.Response):
            self.queue.append(("response", response))
            return self

        def raises(self, exc: Exception):
            self.queue.append(("raise", exc))
            return self

        def __call__(self, url, *args, **kwargs):
            self.calls.append((url, kwargs.get("json")))
            kind, value = self.queue.pop(0) if self.queue else ("raise", RuntimeError("no mock response queued"))
            if kind == "raise":
                raise value
            value.request = httpx.Request("POST", url)
            return value

    mock = MockPost()
    monkeypatch.setattr(httpx.Client, "post", mock)
    return mock
