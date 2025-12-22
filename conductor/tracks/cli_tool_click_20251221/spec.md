# Spec: CLI Tool

## Overview
This track implements the Command Line Interface (CLI) for the Markdown Scraper. It will provide a user-friendly way to invoke the scraping logic from the terminal, supporting both static and dynamic scraping modes, and output configuration.

## User Stories
- As a user, I want to scrape a URL by running a command like `scraper <url>`.
- As a user, I want to save the output to a file using a `--output` flag.
- As a user, I want to enable dynamic scraping using a `--dynamic` flag.
- As a user, I want to see help and usage information.

## Functional Requirements
- Use `click` to build the CLI.
- Expose a main command (e.g., `scrape` or just the entry point) that takes a URL argument.
- Support optional flags:
    - `--output`, `-o`: File path to save the Markdown output.
    - `--dynamic`, `-d`: Enable Playwright-based dynamic scraping.
    - `--strip`, `-s`: List of tags to strip (can be used multiple times).
- Print the Markdown to stdout if no output file is specified.
- Print metadata (title, author) to stderr or in a verbose mode.

## Technical Constraints
- Library: `click`.
- Integration: Must import and use `md_scraper.scraper.Scraper`.
- Package entry point: Configure `pyproject.toml` to create a `scraper` (or `md-scraper`) executable.

## Success Criteria
- User can run `scraper https://example.com` and see Markdown.
- User can run `scraper https://example.com -o result.md` and find the file.
- Help command `scraper --help` displays correct usage.
