import pytest
from md_scraper.crawler import Crawler

def test_crawler_queue_order():
    """Test that the crawler processes items in FIFO order."""
    start_urls = ["https://example.com/1", "https://example.com/2"]
    crawler = Crawler(start_urls)

    # Check initial queue
    assert len(crawler.queue) == 2

    # Process first item
    url, depth = next(crawler)
    assert url == "https://example.com/1"
    assert depth == 0

    # Process second item
    url, depth = next(crawler)
    assert url == "https://example.com/2"
    assert depth == 0

    # Queue should be empty now
    assert not crawler.has_next()
    with pytest.raises(StopIteration):
        next(crawler)

def test_crawler_add_links():
    """Test that add_links appends to the queue."""
    crawler = Crawler(["https://example.com"])
    # consume start url
    next(crawler)

    links = ["https://example.com/child1", "https://example.com/child2"]
    crawler.add_links(links, current_depth=0)

    assert len(crawler.queue) == 2

    url, depth = next(crawler)
    assert url == "https://example.com/child1"
    assert depth == 1

    url, depth = next(crawler)
    assert url == "https://example.com/child2"
    assert depth == 1

def test_crawler_max_depth():
    """Test that links deeper than max_depth are not added."""
    crawler = Crawler(["https://example.com"], max_depth=1)
    # consume start url (depth 0)
    next(crawler)

    # Add child (depth 1) - should be added
    crawler.add_links(["https://example.com/child"], current_depth=0)
    assert len(crawler.queue) == 1

    # Consume child (depth 1)
    url, depth = next(crawler)
    assert depth == 1

    # Add grandchild (depth 2) - should NOT be added because max_depth is 1
    # Note: add_links takes current_depth. If current is 1, next will be 2.
    # The check is: if current_depth >= self.max_depth: return
    crawler.add_links(["https://example.com/grandchild"], current_depth=1)
    assert len(crawler.queue) == 0

def test_crawler_max_pages():
    """Test that crawler stops after max_pages."""
    crawler = Crawler(["https://example.com"], max_pages=2)

    # 1st page
    next(crawler)
    crawler.add_links(["https://example.com/2"], 0)

    # 2nd page
    next(crawler)
    crawler.add_links(["https://example.com/3"], 1)

    # Should stop even if queue is not empty
    assert crawler.crawled_count == 2
    assert crawler.max_pages == 2
    assert not crawler.has_next()

    with pytest.raises(StopIteration):
        next(crawler)

def test_crawler_visited():
    """Test that visited links are not added again."""
    crawler = Crawler(["https://example.com"])
    next(crawler)

    # Add link
    crawler.add_links(["https://example.com/child"], 0)
    assert len(crawler.queue) == 1

    # Consume
    next(crawler)

    # Add same link again
    crawler.add_links(["https://example.com/child"], 0)
    assert len(crawler.queue) == 0

def test_crawler_domain_filtering():
    """Test that links from different domains are ignored if same_domain=True."""
    crawler = Crawler(["https://example.com"], same_domain=True)
    next(crawler)

    links = ["https://example.com/ok", "https://other.com/no"]
    crawler.add_links(links, 0)

    assert len(crawler.queue) == 1
    url, _ = next(crawler)
    assert url == "https://example.com/ok"

def test_crawler_subpath_filtering():
    """Test that links must start with start_url if only_subpaths=True."""
    start_url = "https://example.com/docs"
    crawler = Crawler([start_url], only_subpaths=True)
    next(crawler)

    links = [
        "https://example.com/docs/page1", # OK
        "https://example.com/other",      # NO
        "https://example.com/docs",       # Visited, so NO (but logically OK path)
    ]

    crawler.add_links(links, 0)

    # "https://example.com/docs" is already in visited from start_urls

    assert len(crawler.queue) == 1
    url, _ = next(crawler)
    assert url == "https://example.com/docs/page1"
