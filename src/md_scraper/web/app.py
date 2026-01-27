from flask import Flask, render_template, request, jsonify, send_file
import os
import io
import zipfile
import json
from md_scraper.scraper import Scraper
from md_scraper.crawler import Crawler
from md_scraper.utils import get_title_from_result

app = Flask(__name__)
app.secret_key = os.urandom(24)

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

    scraper = Scraper()
    results = []
    
    try:
        if crawl:
             iterator = Crawler([url], max_depth=depth, max_pages=max_pages, only_subpaths=only_subpaths)
        else:
             iterator = zip([url], [0])
             
        for current_url, current_depth in iterator:
            res = scraper.scrape(current_url, dynamic=dynamic, svg_action=svg_action, image_action=image_action, strip=strip_tags)
            results.append(res)
            
            if crawl and isinstance(iterator, Crawler):
                # Try to get all internal links first
                links = res.get('internal_links') or []
                
                iterator.add_links(links, current_depth)
        
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
            scraper = Scraper()
            
            # If crawling, we use the Crawler for the entire set or per URL?
            # CLI does per URL. Let's do that.
            
            for url in target_urls:
                try:
                    if crawl:
                        iterator = Crawler([url], max_depth=depth, max_pages=max_pages, only_subpaths=only_subpaths)
                    else:
                        iterator = zip([url], [0])
                        
                    for current_url, current_depth in iterator:
                        res = scraper.scrape(current_url, dynamic=dynamic, svg_action=svg_action, image_action=image_action, strip=strip_tags)
                        results.append(res)
                        
                        if crawl and isinstance(iterator, Crawler):
                             # Try to get all internal links first
                            links = res.get('internal_links') or []
                            
                            iterator.add_links(links, current_depth)

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
