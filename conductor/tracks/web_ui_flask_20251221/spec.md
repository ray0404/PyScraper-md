# Spec: Web UI with Flask

## Overview
This track implements a lightweight Web UI for the Markdown Scraper. It allows users to enter a URL into a form, scrape the content (optionally using dynamic mode), and view/copy the resulting Markdown directly in the browser.

## User Stories
- As a user, I want to visit a webpage, enter a URL, and click "Scrape".
- As a user, I want to see the generated Markdown in a text area so I can easily copy it.
- As a user, I want to toggle "Dynamic Mode" from the UI.
- As a user, I want to see a preview of the metadata (title, author) extracted from the page.

## Functional Requirements
- Use `Flask` to serve the application.
- Create a single page with a form containing:
    - URL Input (text)
    - Dynamic Mode (checkbox)
    - Strip Images/Links (checkboxes - optional but good)
    - Submit Button
- Handle form submission via POST or AJAX.
- Use `md_scraper.scraper.Scraper` to process the request.
- Display the result (Markdown and Metadata) on the same page or a results page.
- Handle errors (invalid URL, scrape failure) and display user-friendly messages.

## Technical Constraints
- Library: `flask`.
- Templating: `Jinja2` (built-in to Flask).
- CSS: Minimal custom CSS or a lightweight class-less framework (like Pico.css) to keep it "Clean & Functional" as per guidelines.

## Success Criteria
- User can successfully scrape a URL from the browser.
- Markdown is displayed correctly.
- Dynamic mode toggle works.
