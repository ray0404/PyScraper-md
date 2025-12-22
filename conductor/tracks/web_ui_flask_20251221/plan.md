# Plan: Web UI with Flask

## Phase 1: Flask Setup & Basic Route [checkpoint: 0cc9a25]
- [x] Task: Add `flask` dependency to `pyproject.toml` ac0ca03
- [x] Task: Create `src/md_scraper/web/app.py` with a basic Flask app 79fee73
    - [x] Sub-task: Create `templates/index.html` with a "Hello World" message
    - [x] Sub-task: Configure `poetry` script to run the server (optional, or just use `flask run`)
- [x] Task: Conductor - User Manual Verification 'Phase 1: Flask Setup & Basic Route' (Protocol in workflow.md) 79fee73

## Phase 2: UI Implementation & Integration
- [ ] Task: Design the input form in `templates/index.html`
    - [ ] Sub-task: Add URL input and Dynamic checkbox
- [ ] Task: Implement the scrape logic in the route
    - [ ] Sub-task: Handle POST request
    - [ ] Sub-task: Call `Scraper.scrape`
    - [ ] Sub-task: Render result in the template
- [ ] Task: Add error handling and feedback messages (Flash messages)
- [ ] Task: Write integration tests for the Flask app using `pytest-flask` (or just `pytest` with `client` fixture)
- [ ] Task: Conductor - User Manual Verification 'Phase 2: UI Implementation & Integration' (Protocol in workflow.md)
