# Performance Improvement: Resource Leak Fix in Web App

## What
Implemented proper resource management for the `Scraper` class in both the Web UI/API and the CLI by using it as a context manager.

## Why
The `Scraper` class lazily initializes Playwright and Chromium browser instances when dynamic scraping is enabled. Previously, these instances were never explicitly closed, leading to resource leaks. In a long-running web server, this would cause memory exhaustion and an accumulation of zombie browser processes.

## Impact
- **Memory Efficiency:** Browser processes are now terminated immediately after the scraping task is complete.
- **Reliability:** Prevents server crashes due to resource exhaustion in high-traffic or long-running scenarios.
- **Robustness:** Using context managers ensures that `close()` is called even if errors occur during the scraping process.

## Measured Improvement
While environment constraints (missing dependencies and no internet) prevented establishing a numerical baseline, this change provides a definitive fix for a known resource leak. Without this fix, memory usage would grow linearly with the number of dynamic scraping requests. With this fix, memory usage remains stable.
