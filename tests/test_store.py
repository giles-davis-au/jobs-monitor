from jobsmonitor.models import Job, LocationConfidence
from jobsmonitor.store import Store


def test_dedup_is_new_then_seen(tmp_path):
    store = Store(tmp_path / "test.db")
    job = Job("Block", "123", "Program Manager", "https://x/1", "Sydney")

    assert store.is_new("Block", "123") is True
    store.mark_seen(job, LocationConfidence.CITY)
    assert store.is_new("Block", "123") is False

    # different company, same job_id, is a different dedup key
    assert store.is_new("OtherCo", "123") is True
    store.close()


def test_run_history_and_last_ok_jobs_fetched(tmp_path):
    store = Store(tmp_path / "test.db")

    store.record_run("Block", "ok", 193, 2)
    store.record_run("Block", "error", None, 0, error="timeout")

    assert store.last_ok_jobs_fetched("Block") == 193  # ignores the later error run

    runs = store.recent_runs("Block")
    assert len(runs) == 2
    assert runs[0]["status"] == "error"  # most recent first
    store.close()


def test_last_ok_jobs_fetched_none_when_never_succeeded(tmp_path):
    store = Store(tmp_path / "test.db")
    store.record_run("Block", "error", None, 0, error="boom")
    assert store.last_ok_jobs_fetched("Block") is None
    store.close()
