import time
import re

# Mocking BeautifulSoup Tag for the purpose of benchmark
class MockTag:
    def __init__(self, content):
        self.content = content
    def __str__(self):
        # Walking a BS4 tree to generate a string is moderately expensive.
        # Let's add a small delay to simulate this.
        time.sleep(0.005) # 5ms delay
        return self.content

def current_logic(tags, base_text):
    placeholders = {}
    for i, tag in enumerate(tags):
        placeholder = f"MDScraperSVG{i}"
        placeholders[placeholder] = str(tag) # Immediate stringification

    markdown = base_text
    # Restore preserved SVGs (Multiple replaces)
    for placeholder, content in placeholders.items():
        markdown = markdown.replace(placeholder, content)
    return markdown

def optimized_logic(tags, base_text):
    placeholders = {}
    for i, tag in enumerate(tags):
        placeholder = f"MDScraperSVG{i}"
        placeholders[placeholder] = tag # Store object

    markdown = base_text
    # Single-pass restoration using re.sub with callback for efficiency
    if placeholders:
        pattern = re.compile("|".join(re.escape(k) for k in placeholders.keys()))
        # This calls str(tag) only for found placeholders, lazily.
        # If markdown generation removed some placeholders, it would save calls.
        # Even if not, single-pass replace is generally faster for many keys.
        markdown = pattern.sub(lambda m: str(placeholders[m.group(0)]), markdown)
    return markdown

def run_benchmark(num_tags=100, iterations=10):
    tags = [MockTag(f"<svg id='{i}'>...</svg>") for i in range(num_tags)]
    base_text = "Baseline markdown content.\n" + "\n".join([f"SVG here: MDScraperSVG{i}" for i in range(num_tags)])

    print(f"Running benchmark with {num_tags} tags and {iterations} iterations...")

    start = time.time()
    for _ in range(iterations):
        current_logic(tags, base_text)
    end = time.time()
    current_total = end - start
    print(f"Current logic: {current_total:.4f}s")

    start = time.time()
    for _ in range(iterations):
        optimized_logic(tags, base_text)
    end = time.time()
    optimized_total = end - start
    print(f"Optimized logic: {optimized_total:.4f}s")

    improvement = (current_total - optimized_total) / current_total * 100
    print(f"Improvement: {improvement:.2f}%")

if __name__ == "__main__":
    run_benchmark(num_tags=100, iterations=20)
    run_benchmark(num_tags=500, iterations=20)
