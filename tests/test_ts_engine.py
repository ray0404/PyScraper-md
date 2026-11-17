"""Tests for the TypeScript engine bridge (md_scraper.ts_engine) and its
Flask / CLI integration. The real TS CLI is never spawned here — the
subprocess boundary is mocked; live end-to-end checks live in
typescript/tests/side-by-side.test.ts and the manual verification steps.
"""

import io
import json
import zipfile

import pytest
from click.testing import CliRunner
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import md_scraper.ts_engine as ts_engine
from md_scraper.ts_engine import (
    TSEngineUnavailable,
    content_html_ts,
    crawl_ts,
    run_ts_json,
    scrape_ts,
    ts_command,
    wrap_ts,
)
import md_scraper.web.app as web_app
from md_scraper.web.app import app
from md_scraper.cli import cli


# ---------------------------------------------------------------------------
# ts_command() resolution
# ---------------------------------------------------------------------------

def test_ts_command_env_override(monkeypatch):
    monkeypatch.setenv("PYSCRAPER_TS_CMD", "bun run /somewhere/cli.ts")
    assert ts_command() == ["bun", "run", "/somewhere/cli.ts"]


def test_ts_command_prefers_bundled_bun_src(monkeypatch):
    """Bundled src (wheel) wins over the checkout copy when both exist."""
    monkeypatch.delenv("PYSCRAPER_TS_CMD", raising=False)
    monkeypatch.setattr(ts_engine.shutil, "which",
                        lambda name: "/usr/bin/bun" if name == "bun" else None)
    monkeypatch.setattr(ts_engine.os.path, "exists", lambda p: True)
    assert ts_command() == ["/usr/bin/bun", "run", ts_engine._BUNDLED_SRC_CLI]


def test_ts_command_checkout_src_when_no_bundled(monkeypatch):
    monkeypatch.delenv("PYSCRAPER_TS_CMD", raising=False)
    monkeypatch.setattr(ts_engine.shutil, "which",
                        lambda name: "/usr/bin/bun" if name == "bun" else None)
    monkeypatch.setattr(ts_engine.os.path, "exists",
                        lambda p: p == ts_engine._TS_SRC_CLI)
    assert ts_command() == ["/usr/bin/bun", "run", ts_engine._TS_SRC_CLI]


def test_ts_command_prefers_bundled_dist(monkeypatch):
    """Bundled dist wins over checkout dist when bun is unavailable."""
    monkeypatch.delenv("PYSCRAPER_TS_CMD", raising=False)
    monkeypatch.setattr(ts_engine.shutil, "which",
                        lambda name: "/usr/bin/node" if name == "node" else None)
    monkeypatch.setattr(
        ts_engine.os.path, "exists",
        lambda p: p in (ts_engine._BUNDLED_DIST_CLI, ts_engine._TS_DIST_CLI))
    assert ts_command() == ["/usr/bin/node", ts_engine._BUNDLED_DIST_CLI]


def test_ts_command_npm_bin_fallback(monkeypatch):
    """A globally installed pyscraper-md-ts binary is the last resort."""
    monkeypatch.delenv("PYSCRAPER_TS_CMD", raising=False)
    monkeypatch.setattr(
        ts_engine.shutil, "which",
        lambda name: ("/usr/local/bin/pyscraper-md-ts"
                      if name == "pyscraper-md-ts" else None))
    monkeypatch.setattr(ts_engine.os.path, "exists", lambda p: False)
    assert ts_command() == ["/usr/local/bin/pyscraper-md-ts"]


def test_ts_command_unavailable_names_what_is_missing(monkeypatch):
    monkeypatch.delenv("PYSCRAPER_TS_CMD", raising=False)
    monkeypatch.setattr(ts_engine.shutil, "which", lambda name: None)
    monkeypatch.setattr(ts_engine.os.path, "exists", lambda p: False)
    with pytest.raises(TSEngineUnavailable) as excinfo:
        ts_command()
    assert "pyscraper-md-ts" in str(excinfo.value)
    assert "Bun" in str(excinfo.value)


def test_ts_command_falls_back_to_node_dist(monkeypatch):
    monkeypatch.delenv("PYSCRAPER_TS_CMD", raising=False)
    monkeypatch.setattr(ts_engine.shutil, "which",
                        lambda name: "/usr/bin/node" if name == "node" else None)
    monkeypatch.setattr(ts_engine.os.path, "exists",
                        lambda p: p == ts_engine._TS_DIST_CLI)
    assert ts_command() == ["/usr/bin/node", ts_engine._TS_DIST_CLI]


def test_ts_command_unavailable(monkeypatch):
    monkeypatch.delenv("PYSCRAPER_TS_CMD", raising=False)
    monkeypatch.setattr(ts_engine.shutil, "which", lambda name: None)
    with pytest.raises(TSEngineUnavailable):
        ts_command()


# ---------------------------------------------------------------------------
# run_ts_json()
# ---------------------------------------------------------------------------

def _fake_run(monkeypatch, stdout, returncode=0, stderr=""):
    proc = SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)
    monkeypatch.setattr(ts_engine.subprocess, "run",
                        lambda *a, **k: proc)
    return proc


def test_run_ts_json_success(monkeypatch):
    monkeypatch.setattr(ts_engine, "ts_command", lambda: ["bun", "run", "cli.ts"])
    _fake_run(monkeypatch, '{"markdown": "# Hi"}')
    assert run_ts_json({"op": "scrape", "url": "https://example.com"}) == {
        "markdown": "# Hi"}


def test_run_ts_json_nonzero_exit(monkeypatch):
    monkeypatch.setattr(ts_engine, "ts_command", lambda: ["bun", "run", "cli.ts"])
    _fake_run(monkeypatch, '{"error": "boom"}', returncode=1, stderr="boom")
    with pytest.raises(RuntimeError, match="boom"):
        run_ts_json({"op": "scrape", "url": "https://example.com"})


def test_run_ts_json_non_json_output(monkeypatch):
    monkeypatch.setattr(ts_engine, "ts_command", lambda: ["bun", "run", "cli.ts"])
    _fake_run(monkeypatch, "not json at all")
    with pytest.raises(RuntimeError, match="non-JSON"):
        run_ts_json({"op": "scrape", "url": "https://example.com"})


def test_run_ts_json_error_key(monkeypatch):
    monkeypatch.setattr(ts_engine, "ts_command", lambda: ["bun", "run", "cli.ts"])
    _fake_run(monkeypatch, '{"error": "fetch failed"}')
    with pytest.raises(RuntimeError, match="fetch failed"):
        run_ts_json({"op": "scrape", "url": "https://example.com"})


def test_run_ts_json_node_env_defaults(monkeypatch):
    """Under Node, the bridge defaults NODE_USE_ENV_PROXY and the CA bundle."""
    monkeypatch.setattr(ts_engine, "ts_command", lambda: ["node", "dist/cli.js"])
    monkeypatch.delenv("NODE_USE_ENV_PROXY", raising=False)
    monkeypatch.delenv("NODE_EXTRA_CA_CERTS", raising=False)
    monkeypatch.setenv("SSL_CERT_FILE", "/etc/ssl/ca-bundle.pem")
    captured = {}

    def _fake(*args, **kwargs):
        captured["env"] = kwargs.get("env")
        return SimpleNamespace(returncode=0, stdout='{"markdown": "# Hi"}',
                               stderr="")

    monkeypatch.setattr(ts_engine.subprocess, "run", _fake)
    run_ts_json({"op": "scrape", "url": "https://example.com"})
    assert captured["env"]["NODE_USE_ENV_PROXY"] == "1"
    assert captured["env"]["NODE_EXTRA_CA_CERTS"] == "/etc/ssl/ca-bundle.pem"


def test_run_ts_json_bun_env_untouched(monkeypatch):
    """Under Bun the bridge does not inject Node-specific variables."""
    monkeypatch.setattr(ts_engine, "ts_command",
                        lambda: ["bun", "run", "cli.ts"])
    monkeypatch.delenv("NODE_USE_ENV_PROXY", raising=False)
    captured = {}

    def _fake(*args, **kwargs):
        captured["env"] = kwargs.get("env")
        return SimpleNamespace(returncode=0, stdout='{"markdown": "# Hi"}',
                               stderr="")

    monkeypatch.setattr(ts_engine.subprocess, "run", _fake)
    run_ts_json({"op": "scrape", "url": "https://example.com"})
    assert "NODE_USE_ENV_PROXY" not in captured["env"]


# ---------------------------------------------------------------------------
# Payload shapes of the convenience wrappers
# ---------------------------------------------------------------------------

def test_scrape_ts_payload(monkeypatch):
    captured = {}

    def _fake(req, timeout=300):
        captured["req"] = req
        return {"url": "u"}

    monkeypatch.setattr(ts_engine, "run_ts_json", _fake)
    scrape_ts("https://example.com", dynamic=True, strip_tags=["script"],
              proxy="http://proxy:8080", assets_dir="/tmp/assets")
    req = captured["req"]
    assert req["op"] == "scrape"
    assert req["url"] == "https://example.com"
    assert req["options"]["dynamic"] is True
    assert req["options"]["strip_tags"] == ["script"]
    assert req["options"]["proxy"] == "http://proxy:8080"
    assert req["options"]["assets_dir"] == "/tmp/assets"


def test_crawl_ts_returns_results_list(monkeypatch):
    monkeypatch.setattr(ts_engine, "run_ts_json",
                        lambda req, timeout=300: {"results": [{"url": "a"}, {"url": "b"}]})
    results = crawl_ts("https://example.com", depth=2, max_pages=5)
    assert [r["url"] for r in results] == ["a", "b"]


def test_wrap_ts_payload(monkeypatch):
    captured = {}

    def _fake(req, timeout=300):
        captured["req"] = req
        return {"html_document": "<!DOCTYPE html>"}

    monkeypatch.setattr(ts_engine, "run_ts_json", _fake)
    assert wrap_ts("<p>x</p>", title="T", source_url="https://example.com",
                   include_base=False) == "<!DOCTYPE html>"
    req = captured["req"]
    assert req["op"] == "wrap"
    assert req["content_html"] == "<p>x</p>"
    assert req["include_base"] is False


def test_content_html_ts_payload(monkeypatch):
    monkeypatch.setattr(ts_engine, "run_ts_json",
                        lambda req, timeout=300: {"html": "<p>x</p>"})
    assert content_html_ts("<html><body><p>x</p></body></html>") == "<p>x</p>"


# ---------------------------------------------------------------------------
# Flask integration
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


_TS_RESULT = {
    "url": "https://example.com",
    "metadata": {"title": "Example Domain", "description": "", "author": "",
                 "date": "", "tags": []},
    "markdown": "# Example Domain",
    "html": "<h1>Example Domain</h1>",
    "html_document": "<!DOCTYPE html><html><body><h1>Example Domain</h1></body></html>",
    "raw_html": "<html><body><h1>Example Domain</h1></body></html>",
    "nav_links": [],
    "internal_links": [],
}


def test_api_scrape_engine_ts(client, monkeypatch):
    calls = []
    monkeypatch.setattr(web_app, "scrape_ts",
                        lambda url, **kw: calls.append(kw) or dict(_TS_RESULT))
    resp = client.post("/api/scrape",
                       json={"url": "https://example.com", "engine": "ts"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["markdown"] == "# Example Domain"
    assert data["html_document"].startswith("<!DOCTYPE html>")
    assert calls, "Flask did not call scrape_ts for engine=ts"


def test_api_scrape_engine_invalid(client):
    resp = client.post("/api/scrape",
                       json={"url": "https://example.com", "engine": "bogus"})
    assert resp.status_code == 400
    assert "engine" in resp.get_json()["error"]


def test_api_scrape_engine_python_default(client, monkeypatch):
    """Without 'engine' the Python path is used (Scraper is mocked)."""
    class MockScraper:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def scrape(self, url, **kwargs):
            return dict(_TS_RESULT)
    monkeypatch.setattr(web_app, "Scraper", MockScraper)
    resp = client.post("/api/scrape", json={"url": "https://example.com"})
    assert resp.status_code == 200
    assert resp.get_json()["markdown"] == "# Example Domain"


def test_download_zip_engine_ts_fills_missing_html(client, monkeypatch):
    monkeypatch.setattr(web_app, "content_html_ts", lambda raw: "<p>x</p>")
    monkeypatch.setattr(web_app, "wrap_ts",
                        lambda html, **kw: "<!DOCTYPE html><html><body><p>x</p></body></html>")
    partial = {"url": "https://example.com",
               "metadata": {"title": "Example Domain"},
               "markdown": "# Example Domain",
               "raw_html": "<html><body><p>x</p></body></html>"}
    resp = client.post("/api/download-zip",
                       json={"results": [partial], "format": "html-document",
                             "engine": "ts"})
    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.data)) as zf:
        names = zf.namelist()
        assert len(names) == 1
        assert zf.read(names[0]).decode().startswith("<!DOCTYPE html>")


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

def test_cli_scrape_engine_ts():
    runner = CliRunner()
    result_payload = {"markdown": "# TS Markdown",
                      "metadata": {"title": "TS Title"},
                      "html": "<h1>TS Title</h1>",
                      "html_document": "<!DOCTYPE html>",
                      "raw_html": "<html></html>"}
    with patch("md_scraper.cli.scrape_ts", return_value=result_payload) as mock_ts:
        result = runner.invoke(cli, ["scrape", "--engine", "ts",
                                     "https://example.com"])
        assert result.exit_code == 0, result.output
        assert "# TS Markdown" in result.output
        mock_ts.assert_called_once()
        assert mock_ts.call_args.kwargs.get("dynamic") is False


def test_cli_scrape_engine_ts_server_payload():
    """With --server, the engine choice is sent to the server instead."""
    runner = CliRunner()
    fake_resp = MagicMock()
    fake_resp.json.return_value = {"markdown": "# Remote", "metadata": {}}
    fake_resp.raise_for_status.return_value = None
    with patch("md_scraper.cli.requests.post",
               return_value=fake_resp) as mock_post:
        result = runner.invoke(cli, ["scrape", "--engine", "ts", "--server",
                                     "http://localhost:8080",
                                     "https://example.com"])
        assert result.exit_code == 0, result.output
        payload = mock_post.call_args.kwargs["json"]
        assert payload["engine"] == "ts"
        assert payload["url"] == "https://example.com"
