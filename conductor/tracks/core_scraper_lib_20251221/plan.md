# Plan: Core Scraper Library

## Phase 1: Project Initialization & Foundation
- [x] Task: Initialize Poetry project and install dependencies (`requests`, `beautifulsoup4`, `markdownify`, `lxml`, `pytest`, `pytest-cov`) ef40ba6
- [ ] Task: Set up project structure (`src/md_scraper/`, `tests/`)
- [ ] Task: Create a basic `Scraper` class with a `fetch_html(url)` method
    - [ ] Sub-task: Write tests for `fetch_html` (success and error cases)
    - [ ] Sub-task: Implement `fetch_html` using `requests`
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Project Initialization & Foundation' (Protocol in workflow.md)

## Phase 2: Content Extraction Logic
- [ ] Task: Implement `extract_main_content(html)` method in `Scraper` class
    - [ ] Sub-task: Write tests with mock HTML containing boilerplate
    - [ ] Sub-task: Implement basic heuristics to identify the main article tag (e.g., `<article>`, `.content`, `#main`)
- [ ] Task: Implement `extract_metadata(html)` method
    - [ ] Sub-task: Write tests for title, author, and date extraction
    - [ ] Sub-task: Implement metadata extraction from `<meta>` tags and OpenGraph data
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Content Extraction Logic' (Protocol in workflow.md)

## Phase 3: Markdown Conversion
- [ ] Task: Implement `to_markdown(html)` method using `markdownify`
    - [ ] Sub-task: Write tests for GFM compatibility (tables, code blocks)
    - [ ] Sub-task: Implement conversion with default GFM settings
- [ ] Task: Implement configuration support for `to_markdown` (e.g., `strip_images`, `strip_links`)
    - [ ] Sub-task: Write tests for configuration toggles
    - [ ] Sub-task: Update `to_markdown` to respect configuration
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Markdown Conversion' (Protocol in workflow.md)

## Phase 4: Integration & Refinement
- [ ] Task: Create a top-level `scrape(url)` function that orchestrates the full flow
    - [ ] Sub-task: Write integration tests using real-world (cached) HTML samples
    - [ ] Sub-task: Implement the `scrape` function returning a `ScrapedContent` object
- [ ] Task: Final code cleanup and documentation of public API
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Integration & Refinement' (Protocol in workflow.md)
