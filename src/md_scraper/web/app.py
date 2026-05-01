from flask import Flask, render_template, request, jsonify, send_file
import os
import io
import zipfile
import json
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from md_scraper.scraper import Scraper
from md_scraper.crawler import Crawler
from md_scraper.utils import get_title_from_result

app = Flask(__name__)
app.secret_key = os.urandom(24)


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
        scraper = Scraper()
        try:
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
        finally:
            try:
                scraper.close()
            except Exception:
                pass

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
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required'}), 400

    url = data['url']
    dynamic = data.get('dynamic', False)
    svg_action = data.get('svg_action', 'image')
    image_action = data.get('image_action', 'remote')
    strip_tags = data.get('strip_tags', [])
    
    # Crawling params
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
        
        # If single URL request without crawl, return dict as before for backward compat?
        # But if crawl is ON, we must return list.
        # To be safe for API, let's keep original behavior for non-crawl single url, 
        # but the request structure implied batch processing might be better.
        # However, the original code returned a single dict for /api/scrape.
        # If crawl is enabled, we return a list of results wrapped in a dict or just the first result?
        # Standard: return list if crawl=True.
        if crawl:
             return jsonify({'results': results})
        else:
             return jsonify(results[0] if results else {})
             
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download_zip', methods=['POST'])
def download_zip():
    data = request.get_json()
    results = data.get('results', [])
    if not results:
        return jsonify({'error': 'No results provided'}), 400

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i, res in enumerate(results):
            url = res.get('url', 'unknown')
            markdown = res.get('markdown', '')
            title = get_title_from_result(res, url)
            filename = f"{title}.md"
            # Ensure unique filenames in ZIP
            if filename in zf.namelist():
                filename = f"{title}_{i}.md"
            zf.writestr(filename, markdown)
    
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='scraped_pages.zip'
    )

@app.route('/', methods=['GET', 'POST'])
def index():
    urls_input = ""
    dynamic = False
    svg_action = 'image'
    image_action = 'remote'
    strip_tags = []
    crawl = False
    depth = 3
    max_pages = 10
    only_subpaths = False
    
    results = []
    error = None
    
    if request.method == 'POST':
        urls_input = request.form.get('urls', '')
        dynamic = 'dynamic' in request.form
        svg_action = request.form.get('svg_action', 'image')
        image_action = request.form.get('image_action', 'remote')
        strip_tags = request.form.getlist('strip_tags')
        
        crawl = 'crawl' in request.form
        try:
            depth = int(request.form.get('depth', 3))
            max_pages = int(request.form.get('max_pages', 10))
        except ValueError:
             depth = 3
             max_pages = 10
        only_subpaths = 'only_subpaths' in request.form
        
        target_urls = [u.strip() for u in urls_input.split('\n') if u.strip()]
        
        # Handle file upload
        if 'batch_file' in request.files:
            file = request.files['batch_file']
            if file.filename != '':
                content = file.read().decode('utf-8')
                file_urls = [u.strip() for u in content.split('\n') if u.strip() and not u.strip().startswith('#')]
                target_urls.extend(file_urls)

        if not target_urls:
            error = "No URLs provided."
        else:
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
            
    return render_template('index.html', 
                           urls_input=urls_input, 
                           dynamic=dynamic, 
                           svg_action=svg_action, 
                           image_action=image_action, 
                           strip_tags=strip_tags, 
                           crawl=crawl,
                           depth=depth,
                           max_pages=max_pages,
                           only_subpaths=only_subpaths,
                           results=results, 
                           error=error)

def create_app():
    return app

if __name__ == "__main__":
    # Use PORT from environment variable or default to 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
