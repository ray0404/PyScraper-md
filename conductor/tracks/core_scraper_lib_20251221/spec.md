# Spec: Core Scraper Library

## Overview
This track focuses on building the foundational Python library for the Markdown Scraper. It will handle fetching static HTML content, extracting the main article content, and converting it into GitHub Flavored Markdown (GFM).

## User Stories
- As a developer, I want to provide a URL and receive the main content of the page as a Markdown string.
- As a developer, I want the Markdown to be clean, without navigation, ads, or footers.
- As a developer, I want to be able to extract metadata like the title, author, and date.

## Functional Requirements
- Fetch HTML from a provided URL using `requests`.
- Parse HTML using `BeautifulSoup4`.
- Identify the "main" content area of a webpage using heuristics (similar to Readability.js).
- Convert extracted HTML elements to GFM using `markdownify`.
- Extract metadata (title, author, date, tags) from meta tags and page structure.
- Support configuration to toggle specific elements (images, links).

## Technical Constraints
- Language: Python 3.10+
- Main Libraries: `requests`, `beautifulsoup4`, `markdownify`, `lxml`.
- Testing: `pytest` with `pytest-cov`.
- Packaging: `Poetry`.

## Success Criteria
- Library can successfully fetch and convert a variety of technical blog posts (Medium, dev.to) to clean Markdown.
- Unit tests cover >80% of the core logic.
- Metadata extraction works for most standard news and blog sites.
