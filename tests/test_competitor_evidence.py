"""Offline STEP 3 competitor evidence safety tests."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from competitor_evidence import eligible


def test_google_redirect_is_not_a_competitor():
    ok, reason = eligible("https://www.google.com/goto?url=opaque")
    assert not ok and "redirect" in reason.lower()


def test_normal_competitor_url_is_eligible():
    assert eligible("https://www.mhfa.org.au/webinars")[0]


def test_non_public_or_unsafe_urls_rejected():
    for url in ("http://example.org", "https://127.0.0.1/x",
                "https://localhost/x", "https://example.test/x",
                "https://user:pass@example.org/"):
        assert not eligible(url)[0]
