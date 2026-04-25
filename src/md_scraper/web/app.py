import os
import io
import zipfile
from flask import Flask, request, jsonify, render_template, send_file
from md_scraper.scraper import Scraper
from md_scraper.utils import get_title_from_result, sanitize_filename
from md_scraper.crawler import Crawler

app = Flask(__name__)

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

    results = []
    
    try:
        with Scraper() as scraper:
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
                with Scraper() as scraper:
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
            except Exception as e:
                error = f"Scraper initialization error: {e}"
            
    return render_template('index.html', 
                           urls_input=urls_input, 
                           results=results, 
                           error=error)

if __name__ == '__main__':
    app.run(debug=True, port=8080)
