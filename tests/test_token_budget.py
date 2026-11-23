"""Offline tests; no provider credentials or network calls."""
import sys
from pathlib import Path
from unittest.mock import patch
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from token_budget import Budget, BudgetExceeded, estimate_input, LIMITS


@pytest.fixture
def budget(tmp_path):
    return Budget(tmp_path / "budget.json", "landing_page", reset=True)


def request(budget, stage="STEP 1", output=1000, estimate=2000, path="/v1/responses"):
    with patch("token_budget.estimate_input", return_value=estimate):
        return budget.reserve(stage, path, {"model": "test", "max_output_tokens" if path.endswith("responses") else "max_completion_tokens": output})


def test_scope_limits(tmp_path):
    assert LIMITS == {"landing_page": 250000, "website": 500000}
    assert Budget(tmp_path / "web.json", "website", reset=True).data["limit"] == 500000


def test_actual_usage_reconciles(budget):
    i, _ = request(budget)
    budget.observe(i, {"usage": {"input_tokens": 1000, "output_tokens": 400, "total_tokens": 1400}})
    assert budget.totals() == {"input_tokens": 1000, "output_tokens": 400, "confirmed_tokens": 1400, "unconfirmed_reserved_tokens": 0}


def test_uncertain_request_persists(budget):
    request(budget)
    reopened = Budget(budget.path, "landing_page")
    assert reopened.totals()["unconfirmed_reserved_tokens"] == 3000


def test_reject_over_budget_and_latch(budget):
    request(budget, estimate=200000, output=40000)
    with pytest.raises(BudgetExceeded):
        request(budget, estimate=10000, output=1000)
    with pytest.raises(BudgetExceeded):
        request(budget)
    assert budget.data["blocked"]
    assert len(budget.data["requests"]) == 1


def test_background_poll_not_double_counted(budget):
    i, _ = request(budget, stage="STEP 5")
    budget.observe(i, {"id": "resp_test", "status": "queued"})
    assert budget.find_response("resp_test") == i
    assert budget.totals()["unconfirmed_reserved_tokens"] == 3000
    response = {"id": "resp_test", "status": "completed", "usage": {"input_tokens": 1500, "output_tokens": 500, "total_tokens": 2000}}
    budget.observe(i, response)
    budget.observe(i, response)
    assert budget.totals()["confirmed_tokens"] == 2000


def test_siteone_chat_usage(budget):
    i, body = request(budget, stage="SiteOne", path="/v1/chat/completions")
    assert body["max_completion_tokens"] == 1000
    budget.observe(i, {"usage": {"prompt_tokens": 1100, "completion_tokens": 500, "total_tokens": 1600}})
    assert budget.totals()["confirmed_tokens"] == 1600


def test_underestimate_stops_future_requests(budget):
    i, _ = request(budget)
    budget.observe(i, {"usage": {"input_tokens": 3100, "output_tokens": 500, "total_tokens": 3600}})
    assert budget.data["blocked"]


def test_image_estimate_ignores_base64():
    small = estimate_input({"input": [{"type": "input_image", "image_url": "data:image/jpeg;base64,abc"}]})
    large = estimate_input({"input": [{"type": "input_image", "image_url": "data:image/jpeg;base64," + "a" * 100000}]})
    assert small == large and small >= 20000


def test_summary_distinguishes_unknown(budget):
    request(budget)
    text = budget.summary()
    assert "3,000" in text and "not billed usage" in text
