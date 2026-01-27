from typing import Set, List, Dict, Optional
from urllib.parse import urlparse
from collections import deque

class Crawler:
    """
    Manages the crawling logic: queue, visited set, depth tracking, and domain filtering.
    """
    def __init__(self, start_urls: List[str], max_depth: int = 3, max_pages: int = 50, same_domain: bool = True, only_subpaths: bool = False):
        # Queue stores tuples of (url, depth)
        self.queue = deque([(url, 0) for url in start_urls])
        self.visited: Set[str] = set(start_urls)
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.same_domain = same_domain
        self.only_subpaths = only_subpaths
        self.crawled_count = 0
        
        # Determine allowed domains from start_urls
        self.allowed_domains = {urlparse(url).netloc for url in start_urls}
        self.start_urls = start_urls

    def __iter__(self):
        return self

    def __next__(self):
        """
        Returns the next URL to scrape and its depth.
        """
        if not self.queue or self.crawled_count >= self.max_pages:
            raise StopIteration
        
        url, depth = self.queue.popleft()
        self.crawled_count += 1
        return url, depth

    def add_links(self, links: List[str], current_depth: int):
        """
        Adds discovered links to the queue if they meet the criteria.
        """
        # If we are already at max_depth, we don't add children
        if current_depth >= self.max_depth:
            return

        for link in links:
            if link in self.visited:
                continue
            
            # Domain Check
            if self.same_domain:
                domain = urlparse(link).netloc
                if domain not in self.allowed_domains:
                    continue
            
            # Subpath Check
            if self.only_subpaths:
                # Must start with at least one of the start_urls
                if not any(link.startswith(s_url) for s_url in self.start_urls):
                    continue
            
            self.visited.add(link)
            self.queue.append((link, current_depth + 1))

    def has_next(self):
        return bool(self.queue) and self.crawled_count < self.max_pages
