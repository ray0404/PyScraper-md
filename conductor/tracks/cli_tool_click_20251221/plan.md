# Plan: CLI Tool

## Phase 1: Basic CLI Structure
- [x] Task: Add `click` dependency to `pyproject.toml` 51a53d3
- [ ] Task: Create `src/md_scraper/cli.py` with a basic `click` command group/command
    - [ ] Sub-task: Implement a simple `hello` command to verify setup
    - [ ] Sub-task: Configure `[tool.poetry.scripts]` in `pyproject.toml` to point to the CLI
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Basic CLI Structure' (Protocol in workflow.md)

## Phase 2: Scrape Command Implementation
- [ ] Task: Implement the `scrape` command logic in `cli.py`
    - [ ] Sub-task: Accept `url` argument
    - [ ] Sub-task: Integrate `Scraper` class to fetch and convert content
    - [ ] Sub-task: Print output to stdout
- [ ] Task: Add CLI tests using `click.testing.CliRunner`
    - [ ] Sub-task: Test successful scrape (mocked)
    - [ ] Sub-task: Test error handling (invalid URL)
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Scrape Command Implementation' (Protocol in workflow.md)

## Phase 3: Advanced Options & Output
- [ ] Task: Add support for `--output` file option
    - [ ] Sub-task: Implement file writing logic
    - [ ] Sub-task: Add tests for file output
- [ ] Task: Add support for `--dynamic` and `--strip` options
    - [ ] Sub-task: Pass these options to the `Scraper.scrape` method
    - [ ] Sub-task: Add tests for option passing
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Advanced Options & Output' (Protocol in workflow.md)
