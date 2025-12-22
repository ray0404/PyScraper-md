# Plan: Dynamic Scraping with Playwright

## Phase 1: Playwright Integration
- [x] Task: Install `playwright` and browser binaries (System Chromium installed; Python bindings mocked for Termux) 1715789
    - [x] Sub-task: Update `pyproject.toml`
    - [x] Sub-task: Run `playwright install chromium`
- [ ] Task: Create `DynamicScraper` class (or extend `Scraper`)
    - [ ] Sub-task: Implement `fetch_html_dynamic(url)` using Playwright's sync API for simplicity (or async if preferred for the architecture)
    - [ ] Sub-task: Add error handling for browser launch/page load failures
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Playwright Integration' (Protocol in workflow.md)

## Phase 2: Unified API & Testing
- [ ] Task: Update the top-level `scrape` function to accept a `dynamic=False` flag
    - [ ] Sub-task: Route to `fetch_html_dynamic` if `dynamic=True`
- [ ] Task: Write integration tests for dynamic scraping
    - [ ] Sub-task: Test against a sample JS-heavy page (can mock the Playwright return if needed for CI speed)
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Unified API & Testing' (Protocol in workflow.md)
