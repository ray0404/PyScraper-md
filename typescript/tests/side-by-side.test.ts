/**
 * side-by-side.test.ts — TS vs Python fixture comparison.
 *
 * The same fixture pages are scraped by both engines (the Python one
 * via a subprocess running the repo's own code) and the outputs are
 * compared field by field. The Python side needs the venv interpreter;
 * the test is skipped when no usable Python is found.
 */
import { test, expect } from "bun:test";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { scrapeNative, type ScrapeResult } from "../src/scraper.js";

const REPO_ROOT = `${import.meta.dir}/../..`;
const SRC_DIR = `${REPO_ROOT}/src`;
const HELPER = `${import.meta.dir}/helpers/py_scrape.py`;

function findPython(): string | null {
  const candidates = [
    process.env.PYSCRAPER_VENV_PYTHON,
    `${process.env.HOME}/workspace/pyscraper-md-venv/bin/python`,
    "python3",
  ].filter(Boolean) as string[];
  for (const candidate of candidates) {
    const proc = spawnSync(
      candidate,
      ["-c", "import sys; sys.path.insert(0, sys.argv[1]); import md_scraper", SRC_DIR],
      { encoding: "utf-8" },
    );
    if (proc.status === 0) return candidate;
  }
  return null;
}

const PYTHON = findPython();

function scrapeWithPython(url: string, options: Record<string, unknown> = {}): ScrapeResult {
  const proc = spawnSync(
    PYTHON as string,
    [HELPER, SRC_DIR, url, JSON.stringify(options)],
    { encoding: "utf-8", maxBuffer: 64 * 1024 * 1024 },
  );
  if (proc.status !== 0) {
    throw new Error(`Python scrape failed: ${proc.stderr}`);
  }
  return JSON.parse(proc.stdout) as ScrapeResult;
}

const FIXTURES = [
  { file: "blog_post.html", url: "https://example.com/blog/sample" },
  { file: "rich.html", url: "https://example.com/rich" },
];

const FIELDS = [
  "url",
  "metadata",
  "markdown",
  "html",
  "html_document",
  "raw_html",
  "nav_links",
  "internal_links",
] as const;

for (const fixture of FIXTURES) {
  test.skipIf(!PYTHON)(
    `side-by-side: ${fixture.file} matches Python field by field`,
    async () => {
      const fixturePath = `${import.meta.dir}/fixtures/${fixture.file}`;
      const py = scrapeWithPython(fixturePath);
      const ts = await scrapeNative(fixturePath);
      // The URL differs by design (the Python run is pointed at the
      // fixture path too, so the URLs agree); compare everything.
      for (const field of FIELDS) {
        expect(ts[field]).toEqual(py[field]);
      }
    },
  );

  test.skipIf(!PYTHON)(
    `side-by-side: ${fixture.file} matches Python with svg strip + image base64`,
    async () => {
      const fixturePath = `${import.meta.dir}/fixtures/${fixture.file}`;
      const options = { svg_action: "strip", image_action: "remote" };
      const py = scrapeWithPython(fixturePath, options);
      const ts = await scrapeNative(fixturePath, {
        svgAction: "strip",
        imageAction: "remote",
      });
      for (const field of FIELDS) {
        expect(ts[field]).toEqual(py[field]);
      }
    },
  );
}
