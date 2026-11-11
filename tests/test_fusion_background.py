"""Offline tests: STEP 5 background transport does not resubmit paid work."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fusion_api import call_fusion_background


def reply(status, response_id="resp_test", text=""):
    return SimpleNamespace(id=response_id, status=status, output_text=text,
                           incomplete_details=None, usage=None, error=None)


class FakeClient:
    def __init__(self, created, polled=()):
        self.created = created
        self.polled = iter(polled)
        self.create_count = 0
        self.retrieve_ids = []
        self.responses = self

    def create(self, **kwargs):
        self.create_count += 1
        assert kwargs["background"] is True
        assert kwargs["reasoning"]["effort"] == "high"
        assert kwargs["input"][1]["content"] == "unchanged evidence"
        if isinstance(self.created, BaseException):
            raise self.created
        return self.created

    def retrieve(self, response_id, **kwargs):
        self.retrieve_ids.append(response_id)
        r = next(self.polled)
        if isinstance(r, BaseException):
            raise r
        return r


def run(client, tmp_path, **kwargs):
    return call_fusion_background(client, "test-model", "unchanged prompt",
                                  "unchanged evidence", {"sample": 3},
                                  tmp_path / "diagnostics.json",
                                  sleep_fn=lambda _: None, **kwargs)


def test_background_poll_returns_report_without_repeat_create(tmp_path):
    client = FakeClient(reply("queued"), [reply("in_progress"),
                                         reply("completed", text="Useful report")])
    assert run(client, tmp_path) == "Useful report"
    assert client.create_count == 1
    assert client.retrieve_ids == ["resp_test", "resp_test"]
    diagnostics = json.loads((tmp_path / "diagnostics.json").read_text())
    assert diagnostics["response_id"] == "resp_test"
    assert diagnostics["outcome"] == "completed"
    assert "unchanged evidence" not in (tmp_path / "diagnostics.json").read_text()


def test_transient_poll_disconnect_reuses_id(tmp_path):
    error = APIConnectionError(request=httpx.Request("GET", "https://api.openai.com/v1/responses/resp_test"))
    client = FakeClient(reply("in_progress"), [error, reply("completed", text="Recovered")])
    assert run(client, tmp_path) == "Recovered"
    assert client.create_count == 1
    assert client.retrieve_ids == ["resp_test", "resp_test"]
    diagnostics = json.loads((tmp_path / "diagnostics.json").read_text())
    assert diagnostics["poll_connection_errors"] == 1


def test_uncertain_creation_never_auto_resubmits(tmp_path):
    error = APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    client = FakeClient(error)
    with pytest.raises(APIConnectionError):
        run(client, tmp_path)
    assert client.create_count == 1
    diag = json.loads((tmp_path / "diagnostics.json").read_text())
    assert diag["outcome"] == "creation_unconfirmed_no_auto_resubmit"


def test_incomplete_result_not_published(tmp_path):
    client = FakeClient(reply("completed", text=""))
    with pytest.raises(RuntimeError, match="complete nonempty"):
        run(client, tmp_path)
    assert client.create_count == 1


def test_poll_deadline_retains_response_id(tmp_path):
    client = FakeClient(reply("in_progress"))
    with pytest.raises(TimeoutError):
        run(client, tmp_path, clock_fn=lambda: 1000, max_wait_seconds=-1)
    diag = json.loads((tmp_path / "diagnostics.json").read_text())
    assert diag["response_id"] == "resp_test"
    assert diag["outcome"] == "polling_deadline_reached_response_still_available"
