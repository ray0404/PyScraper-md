"""Bridge to the TypeScript engine (``typescript/``) from Python.

The TS engine is invoked as a subprocess through its ``--json`` machine
mode (see ``typescript/src/cli.ts``): one JSON request on stdin, one JSON
result on stdout. This keeps the Python side free of any Node/Bun
dependency at import time — the TS engine is only needed when the
caller explicitly asks for ``engine="ts"``.

How the TS CLI is located (first match wins):

1. ``PYSCRAPER_TS_CMD`` — a full command line, e.g.
   ``bun run /path/to/typescript/src/cli.ts`` or
   ``node /path/to/typescript/dist/cli.js``.
2. The copy bundled in the wheel: ``typescript/`` sits next to the
   ``md_scraper`` package (``site-packages/typescript/``, added via
   ``[tool.poetry] include`` in ``pyproject.toml``) — ``src/cli.ts``
   run with ``bun`` if present, else ``dist/cli.js`` run with ``node``.
   A wheel install has no repo checkout, so this is the only copy it has.
3. A repo checkout: ``typescript/`` at the repo root (dev installs) —
   again ``src/cli.ts`` + ``bun`` first, then ``dist/cli.js`` + ``node``.
4. A globally installed ``pyscraper-md-ts`` binary on PATH (the
   published npm package's ``bin``) — run directly, it is ``dist/cli.js``.

The subprocess inherits this process's environment, so proxy settings
for dynamic scraping (``PYSCRAPER_PROXY``, ``CHROMIUM_PATH``) flow
through unchanged.

Note: engine="ts" still needs Bun or Node on PATH at runtime — Poetry
cannot install a JavaScript runtime. Only the TS *sources* are bundled
in the wheel; there is no build step at install time (wheels run no
code on install), so ``dist/`` must be built at packaging time
(``scripts/build-wheel.sh``) for the Node path to exist in the wheel.
"""

import json
import os
import shlex
import shutil
import subprocess
from typing import Any, Dict, List, Optional

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_TS_DIR = os.path.join(_REPO_ROOT, "typescript")
_TS_SRC_CLI = os.path.join(_TS_DIR, "src", "cli.ts")
_TS_DIST_CLI = os.path.join(_TS_DIR, "dist", "cli.js")

# Copy bundled in the wheel: typescript/ sits next to the md_scraper
# package (site-packages/typescript/), not inside it — poetry-core 2.x
# cannot map a non-Python tree into a package (packages entries require
# a .py file; include entries have no target). See pyproject.toml.
_PACKAGE_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BUNDLED_TS_DIR = os.path.join(_PACKAGE_PARENT, "typescript")
_BUNDLED_SRC_CLI = os.path.join(_BUNDLED_TS_DIR, "src", "cli.ts")
_BUNDLED_DIST_CLI = os.path.join(_BUNDLED_TS_DIR, "dist", "cli.js")


class TSEngineUnavailable(RuntimeError):
    """Raised when the TS engine cannot be located or started."""


def ts_command() -> List[str]:
    """Return the argv prefix that runs the TS CLI (without ``--json``)."""
    override = os.environ.get("PYSCRAPER_TS_CMD")
    if override:
        return shlex.split(override)
    bun = shutil.which("bun")
    if bun and os.path.exists(_BUNDLED_SRC_CLI):
        return [bun, "run", _BUNDLED_SRC_CLI]
    node = shutil.which("node")
    if node and os.path.exists(_BUNDLED_DIST_CLI):
        return [node, _BUNDLED_DIST_CLI]
    if bun and os.path.exists(_TS_SRC_CLI):
        return [bun, "run", _TS_SRC_CLI]
    if node and os.path.exists(_TS_DIST_CLI):
        return [node, _TS_DIST_CLI]
    npm_bin = shutil.which("pyscraper-md-ts")
    if npm_bin:
        return [npm_bin]
    raise TSEngineUnavailable(
        "TypeScript engine is not available: no bundled typescript/ tree "
        "was found next to the md_scraper package, no repo checkout was "
        "found, and no pyscraper-md-ts binary is on PATH. Install Bun "
        "(then bun run typescript/src/cli.ts works), build the TS package "
        "(cd typescript && npm run build) so typescript/dist/cli.js exists, "
        "or install the published engine (npm install -g pyscraper-md-ts)."
    )


def run_ts_json(request: Dict[str, Any], timeout: int = 300) -> Dict[str, Any]:
    """Send one JSON request to the TS CLI's --json mode; return the parsed result.

    Raises RuntimeError if the CLI exits non-zero, returns non-JSON, or
    returns a JSON ``{"error": ...}`` object.
    """
    cmd = ts_command() + ["--json"]
    # Node's fetch only honours proxy env vars when NODE_USE_ENV_PROXY=1
    # and only trusts extra CAs via NODE_EXTRA_CA_CERTS (it ignores
    # SSL_CERT_FILE, which Bun and curl/requests do honour). Default both
    # from the ambient environment when running under Node so the Node
    # path works wherever the Bun path does (e.g. a systemd service whose
    # unit sets the proxy + SSL_CERT_FILE but not the Node-specific vars).
    env = dict(os.environ)
    if os.path.basename(cmd[0]) in ("node", "pyscraper-md-ts"):
        env.setdefault("NODE_USE_ENV_PROXY", "1")
        if "NODE_EXTRA_CA_CERTS" not in env and "SSL_CERT_FILE" in env:
            env["NODE_EXTRA_CA_CERTS"] = env["SSL_CERT_FILE"]
    proc = subprocess.run(
        cmd,
        input=json.dumps(request),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(
            "TS engine returned non-JSON output: "
            f"{proc.stdout[:500]!r} (stderr: {proc.stderr[:500]!r})"
        )
    if proc.returncode != 0 or "error" in data:
        raise RuntimeError(
            f"TS engine failed: {data.get('error', proc.stderr[:500])}"
        )
    return data


def scrape_ts(url: str, dynamic: bool = False, svg_action: str = "image",
              image_action: str = "remote", strip_tags: Optional[List[str]] = None,
              proxy: Optional[str] = None, user_agent: Optional[str] = None,
              delay: float = 0.0, retries: int = 3,
              ignore_https_errors: bool = False,
              assets_dir: Optional[str] = None) -> Dict[str, Any]:
    """Scrape one URL with the TS engine; returns the ScrapeResult dict."""
    return run_ts_json({
        "op": "scrape",
        "url": url,
        "options": {
            "dynamic": dynamic,
            "svg_action": svg_action,
            "image_action": image_action,
            "assets_dir": assets_dir,
            "strip_tags": list(strip_tags) if strip_tags else [],
            "proxy": proxy,
            "user_agent": user_agent,
            "delay": delay,
            "retries": retries,
            "ignore_https_errors": ignore_https_errors,
        },
    })


def crawl_ts(url: str, dynamic: bool = False, svg_action: str = "image",
             image_action: str = "remote", strip_tags: Optional[List[str]] = None,
             proxy: Optional[str] = None, user_agent: Optional[str] = None,
             delay: float = 0.0, retries: int = 3,
             ignore_https_errors: bool = False,
             assets_dir: Optional[str] = None,
             depth: int = 3, max_pages: int = 10,
             only_subpaths: bool = False) -> List[Dict[str, Any]]:
    """Crawl from one URL with the TS engine; returns a list of results."""
    data = run_ts_json({
        "op": "scrape",
        "url": url,
        "options": {
            "dynamic": dynamic,
            "svg_action": svg_action,
            "image_action": image_action,
            "assets_dir": assets_dir,
            "strip_tags": list(strip_tags) if strip_tags else [],
            "proxy": proxy,
            "user_agent": user_agent,
            "delay": delay,
            "retries": retries,
            "ignore_https_errors": ignore_https_errors,
            "crawl": True,
            "depth": depth,
            "max_pages": max_pages,
            "only_subpaths": only_subpaths,
        },
    })
    return data["results"]


def wrap_ts(content_html: str, title: Optional[str] = None,
            source_url: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None,
            include_base: bool = True) -> str:
    """Wrap content HTML in a standalone document using the TS engine."""
    return run_ts_json({
        "op": "wrap",
        "content_html": content_html,
        "title": title,
        "source_url": source_url,
        "metadata": metadata or {},
        "include_base": include_base,
    })["html_document"]


def content_html_ts(raw_html: str) -> str:
    """Extract content HTML from a raw document using the TS engine."""
    return run_ts_json({
        "op": "content_html",
        "raw_html": raw_html,
    })["html"]
