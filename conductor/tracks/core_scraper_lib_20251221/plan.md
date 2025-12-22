# Plan: Core Scraper Library

## Phase 1: Project Initialization & Foundation [checkpoint: 6e59b10]
- [x] Task: Initialize Poetry project and install dependencies (`requests`, `beautifulsoup4`, `markdownify`, `lxml`, `pytest`, `pytest-cov`) ef40ba6
- [x] Task: Set up project structure (`src/md_scraper/`, `tests/`) 4a7b95f
- [x] Task: Create a basic `Scraper` class with a `fetch_html(url)` method 68256e7
    - [x] Sub-task: Write tests for `fetch_html` (success and error cases)
    - [x] Sub-task: Implement `fetch_html` using `requests`
- [x] Task: Conductor - User Manual Verification 'Phase 1: Project Initialization & Foundation' (Protocol in workflow.md) 6e59b10

## Phase 2: Content Extraction Logic
- [x] Task: Implement `extract_main_content(html)` method in `Scraper` class 2ca6e56
    - [x] Sub-task: Write tests with mock HTML containing boilerplate
    - [x] Sub-task: Implement basic heuristics to identify the main article tag (e.g., `<article>`, `.content`, `#main`)
- [x] Task: Implement `extract_metadata(html)` method 1715789
    - [x] Sub-task: Write tests for title, author, and date extraction
    - [x] Sub-task: Implement metadata extraction from `<meta>` tags and OpenGraph data
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Content Extraction Logic' (Protocol in workflow.md)

## Phase 3: Markdown Conversion
- [x] Task: Implement `to_markdown(html)` method using `markdownify` e342a30
    - [x] Sub-task: Write tests for GFM compatibility (tables, code blocks)
    - [x] Sub-task: Implement conversion with default GFM settings
- [x] Task: Implement configuration support for `to_markdown` (e.g., `strip_images`, `strip_links`) e342a30
    - [x] Sub-task: Write tests for configuration toggles
    - [x] Sub-task: Update `to_markdown` to respect configuration
- [x] Task: Conductor - User Manual Verification 'Phase 3: Markdown Conversion' (Protocol in workflow.md) e342a30

## Phase 4: Integration & Refinement
- [x] Task: Create a top-level `scrape(url)` function that orchestrates the full flow 13289b5
    - [x] Sub-task: Write integration tests using real-world (cached) HTML samples
    - [x] Sub-task: Implement the `scrape` function returning a `ScrapedContent` object
- [x] Task: Final code cleanup and documentation of public API 3c89956
- [x] Task: Conductor - User Manual Verification 'Phase 4: Integration & Refinement' (Protocol in workflow.md) 13289b5
