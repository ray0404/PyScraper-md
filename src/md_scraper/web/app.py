import os
import io
import zipfile
import json
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify, render_template, send_file
from md_scraper.scraper import Scraper
from md_scraper.utils import get_title_from_result, sanitize_filename
from md_scraper.crawler import Crawler

app = Flask(__name__)

def process_crawling(iterator, crawl, dynamic, svg_action, image_action, strip_tags):
    # Determine the start URL and whether it's a batch
    # We will just manage a thread pool and a task queue
    # Actually, we can use a simpler approach:
    # `iterator` is either `Crawler` or `zip`.

    results = []
    task_queue = queue.Queue()
    result_queue = queue.Queue()

    active_tasks = 0
    active_tasks_lock = threading.Lock()

    # Initialize task queue from iterator
    # Note: If it's a zip object, we can just iterate over it fully
    # If it's a Crawler, it yields the first URL
    try:
        if crawl and hasattr(iterator, 'has_next'):
            # It's a crawler. We don't exhaust it, we just pull the first one
            # Actually, `Crawler` queue might have multiple start_urls if it's passed a list
            # We can pull all currently available URLs
            while iterator.has_next():
                try:
                    task_queue.put(next(iterator))
                    with active_tasks_lock:
                        active_tasks += 1
                except StopIteration:
                    break
        else:
            for item in iterator:
                task_queue.put(item)
                with active_tasks_lock:
                    active_tasks += 1
    except StopIteration:
        pass

    if active_tasks == 0:
        return results

    def worker():
        # Each thread gets its own Scraper
        with Scraper() as scraper:
            while True:
                item = task_queue.get()
                if item is None:
                    # Sentinel value to terminate
                    task_queue.task_done()
                    break

                url, depth = item
                try:
                    res = scraper.scrape(
                        url,
                        dynamic=dynamic,
                        svg_action=svg_action,
                        image_action=image_action,
                        strip=strip_tags
                    )
                    result_queue.put((res, depth, None))
                except Exception as e:
                    result_queue.put((None, depth, e))
                finally:
                    task_queue.task_done()

    # Start workers
    num_workers = min(5, active_tasks) if active_tasks > 0 else 5
    # If crawl is true, we might discover more tasks, so always start max_workers
    if crawl: num_workers = 5

    threads = []
    for _ in range(num_workers):
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)

    # Main thread handles results and feeding the Crawler queue
    try:
        while True:
            with active_tasks_lock:
                if active_tasks == 0:
                    break

            res, depth, error = result_queue.get()

            if error is None:
                results.append(res)
                if crawl and hasattr(iterator, 'add_links'):
                    links = res.get('internal_links') or []
                    iterator.add_links(links, depth)

                    # After adding links, the Crawler queue might have new items
                    while iterator.has_next():
                        try:
                            task_queue.put(next(iterator))
                            with active_tasks_lock:
                                active_tasks += 1
                        except StopIteration:
                            break
            else:
                # If single URL, raise so caller handles it
                if not crawl:
                    raise error

            with active_tasks_lock:
                active_tasks -= 1
    finally:
        # Stop workers
        for _ in range(num_workers):
            task_queue.put(None)
        for t in threads:
            t.join()

    return results

@app.route('/api/scrape', methods=['POST'])
def api_scrape():
    data = request.json
    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required'}), 400

    url = data.get('url')
    dynamic = data.get('dynamic', False)
    svg_action = data.get('svg_action', 'image')
    image_action = data.get('image_action', 'remote')
    strip_tags = data.get('strip_tags', [])
    crawl = data.get('crawl', False)
    depth = int(data.get('depth', 3))
    max_pages = int(data.get('max_pages', 10))
    only_subpaths = data.get('only_subpaths', False)

    try:
        if crawl:
             iterator = Crawler([url], max_depth=depth, max_pages=max_pages, only_subpaths=only_subpaths)
        else:
             iterator = zip([url], [0])
             
        results = process_crawling(iterator, crawl, dynamic, svg_action, image_action, strip_tags)
        
        # Return a list of results when crawling to support multiple pages.
        # For a single URL request (crawl=False), return a single dict for backward compatibility.
        if crawl:
             return jsonify({'results': results})
        else:
             return jsonify(results[0])
             
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-zip', methods=['POST'])
def download_zip():
    data = request.json
    results = data.get('results', [])
    if not results:
        return jsonify({'error': 'No results provided'}), 400

    memory_file = io.BytesIO()
    used_filenames = set()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i, res in enumerate(results):
            url = res.get('url', 'unknown')
            markdown = res.get('markdown', '')
            title = get_title_from_result(res, url)
            filename = f"{title}.md"
            # Ensure unique filenames in ZIP
            if filename in used_filenames:
                filename = f"{title}_{i}.md"
            zf.writestr(filename, markdown)
            used_filenames.add(filename)
    
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='scraped_content.zip'
    )

@app.route('/', methods=['GET', 'POST'])
def index():
    results = []
    error = None
    urls_input = ""
    
    if request.method == 'POST':
        urls_input = request.form.get('urls', '')
        dynamic = 'dynamic' in request.form
        svg_action = request.form.get('svg_action', 'image')
        image_action = request.form.get('image_action', 'remote')
        strip_tags = request.form.getlist('strip')
        crawl = 'crawl' in request.form
        depth = int(request.form.get('depth', 3))
        max_pages = int(request.form.get('max_pages', 10))
        only_subpaths = 'only_subpaths' in request.form

        target_urls = [u.strip() for u in urls_input.split('\n') if u.strip()]
        
        if not target_urls:
            error = "No URLs provided."
        else:
            try:
                # If crawling, we use the Crawler for the entire set or per URL?
                # CLI does per URL. Let's do that.
                
                for url in target_urls:
                    try:
                        if crawl:
                            iterator = Crawler([url], max_depth=depth, max_pages=max_pages, only_subpaths=only_subpaths)
                        else:
                            iterator = zip([url], [0])
                            
                        batch_results = process_crawling(iterator, crawl, dynamic, svg_action, image_action, strip_tags)
                        results.extend(batch_results)

                    except Exception as e:
                        error = f"Error scraping {url}: {e}"
                        # We continue with other URLs if one fails
            except Exception as e:
                error = f"Scraper initialization error: {e}"
            
    return render_template('index.html', 
                           urls_input=urls_input, 
                           results=results, 
                           error=error)

if __name__ == '__main__':
    app.run(debug=True, port=8080)
