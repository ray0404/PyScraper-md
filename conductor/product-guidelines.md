# Product Guidelines - Markdown Scraper

## Communication & Tone
- **Professional & Technical:** Messaging within the CLI and Web UI should be clear, concise, and focused on functional details. Avoid unnecessary jargon where a simple term suffices, but remain precise.

## Documentation & Code Style
- **Comprehensive API Reference:** All public-facing functions, classes, and modules MUST include extensive docstrings (Google or NumPy style).
- **Type Hinting:** Use Python type hints throughout the codebase to enhance maintainability and developer experience.
- **Example-Driven:** Documentation should provide clear usage examples for both the library and CLI.

## User Experience & Interface
- **Clean & Functional Web UI:** The web interface should be distraction-free, focusing on the core task of inputting URLs and viewing/copying the resulting Markdown.
- **Action-Oriented Errors:** Error messages should be descriptive and, whenever possible, suggest a corrective action for the user.

## Data & Output Standards
- **Standardized Markdown:** Output MUST strictly follow GitHub Flavored Markdown (GFM) to ensure maximum compatibility.
- **Configurable Output:** Users should have the ability to toggle specific Markdown elements (e.g., images, links, or headers) via configuration or CLI flags.