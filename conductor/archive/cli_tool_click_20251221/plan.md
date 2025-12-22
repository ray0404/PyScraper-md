# Plan: CLI Tool

## Phase 1: Basic CLI Structure [checkpoint: 59a3072]
- [x] Task: Add `click` dependency to `pyproject.toml` 51a53d3
- [x] Task: Create `src/md_scraper/cli.py` with a basic `click` command group/command cca08b3
    - [x] Sub-task: Implement a simple `hello` command to verify setup
    - [x] Sub-task: Configure `[tool.poetry.scripts]` in `pyproject.toml` to point to the CLI
- [x] Task: Conductor - User Manual Verification 'Phase 1: Basic CLI Structure' (Protocol in workflow.md) cca08b3

## Phase 2: Scrape Command Implementation
- [x] Task: Implement the `scrape` command logic in `cli.py` 9e12672
    - [x] Sub-task: Accept `url` argument
    - [x] Sub-task: Integrate `Scraper` class to fetch and convert content
    - [x] Sub-task: Print output to stdout
- [x] Task: Add CLI tests using `click.testing.CliRunner` 9e12672
    - [x] Sub-task: Test successful scrape (mocked)
    - [x] Sub-task: Test error handling (invalid URL)
- [x] Task: Conductor - User Manual Verification 'Phase 2: Scrape Command Implementation' (Protocol in workflow.md) 9e12672

## Phase 3: Advanced Options & Output
- [x] Task: Add support for `--output` file option d922cb8
    - [x] Sub-task: Implement file writing logic
    - [x] Sub-task: Add tests for file output
- [x] Task: Add support for `--dynamic` and `--strip` options d922cb8
    - [x] Sub-task: Pass these options to the `Scraper.scrape` method
    - [x] Sub-task: Add tests for option passing
- [x] Task: Conductor - User Manual Verification 'Phase 3: Advanced Options & Output' (Protocol in workflow.md) d922cb8
