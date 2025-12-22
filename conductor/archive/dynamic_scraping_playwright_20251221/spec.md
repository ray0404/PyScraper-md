# Spec: Dynamic Scraping with Playwright

## Overview
This track adds the capability to scrape modern, JavaScript-heavy websites (Single Page Applications) that require client-side rendering. We will integrate `playwright` into the scraping pipeline to render pages before extracting content.

## User Stories
- As a developer, I want to scrape websites that load content via JavaScript (React, Vue, Angular apps).
- As a developer, I want the option to toggle between fast static scraping (Requests) and robust dynamic scraping (Playwright).

## Functional Requirements
- Install and configure `playwright`.
- Implement a method to fetch rendered HTML using a headless browser.
- Ensure the existing extraction and conversion logic (metadata, main content, markdown) works seamlessly with the rendered HTML.
- Support configuration options for the browser (e.g., headless mode, user agent, timeout).

## Technical Constraints
- Library: `playwright`.
- Async support: Playwright is natively async; we may need to expose an async API or manage the event loop for the synchronous API.
- Testing: Integration tests against a local server or public dynamic site (mocked if possible).

## Success Criteria
- Successfully scrape a JS-rendered page that fails with standard `requests`.
- Unit/Integration tests cover the Playwright execution path.
