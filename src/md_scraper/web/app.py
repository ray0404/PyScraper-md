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

def process_crawling(iterator, crawl, dynamic, svg_action, image_action, strip_tags, proxy=None, user_agent=None, delay=0.0, retries=3):
    # Determine the start URL and whether it's a batch
    # We will just manage a thread pool and a task queue
    # `iterator` is either `Crawler` or `zip`.

    results = []
    task_queue = queue.Queue()
    result_queue = queue.Queue()

    active_tasks = 0
    active_tasks_lock = threading.Lock()

    # Initialize task queue from iterator
    try:
        if crawl and hasattr(iterator, 'has_next'):
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
        while True:
            item = task_queue.get()
            if item is None:
                task_queue.task_done()
                break

            url, depth = item
            try:
                try:
                    scraper_cm = Scraper(proxy=proxy, user_agent=user_agent, delay=delay, retries=retries)
                except TypeError:
                    scraper_cm = Scraper()

                with scraper_cm as scraper:
                    res = scraper.scrape(
                        url,
                        dynamic=dynamic,
                        svg_action=svg_action,
                        image_action=image_action,
                        strip=strip_tags,
                        proxy=proxy,
                        user_agent=user_agent,
                        delay=delay,
                        retries=retries
                    )
                    result_queue.put((res, depth, None))
            except Exception as e:
                result_queue.put((None, depth, e))
            finally:
                task_queue.task_done()

    # Start workers
    num_workers = min(5, active_tasks) if active_tasks > 0 else 5
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

                    while iterator.has_next():
                        try:
                            task_queue.put(next(iterator))
                            with active_tasks_lock:
                                active_tasks += 1
                        except StopIteration:
                            break
            else:
                if not crawl:
                    raise error

            with active_tasks_lock:
                active_tasks -= 1
    finally:
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
    proxy = data.get('proxy')
    user_agent = data.get('user_agent')
    delay = float(data.get('delay', 0.0))
    retries = int(data.get('retries', 3))

    try:
        if crawl:
             iterator = Crawler([url], max_depth=depth, max_pages=max_pages, only_subpaths=only_subpaths)
        else:
             iterator = zip([url], [0])
             
        results = process_crawling(
            iterator, crawl, dynamic, svg_action, image_action, strip_tags,
            proxy=proxy, user_agent=user_agent, delay=delay, retries=retries
        )
        
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
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=True, host=host, port=port)
