"""Smoke test: every major page renders for a logged-in admin."""
import pytest

PAGES = [
    "/dashboard", "/contacts", "/contacts?list=all", "/contacts?list=suppression",
    "/campaigns", "/campaigns/new", "/sender", "/verification", "/templates",
    "/domains", "/reports", "/settings", "/billing", "/team", "/automation",
    "/admin",
]


@pytest.mark.parametrize("path", PAGES)
def test_page_renders(auth, path):
    assert auth.get(path).status_code in (200, 302)
