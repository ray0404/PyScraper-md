from flask import Flask, render_template, request, jsonify, send_file
import os
import io
import zipfile
import json
from md_scraper.scraper import Scraper
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

    scraper = Scraper()
    try:
        result = scraper.scrape(url, dynamic=dynamic, svg_action=svg_action, image_action=image_action, strip=strip_tags)
        return jsonify(result)
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
    results = []
    error = None
    
    if request.method == 'POST':
        urls_input = request.form.get('urls', '')
        dynamic = 'dynamic' in request.form
        svg_action = request.form.get('svg_action', 'image')
        image_action = request.form.get('image_action', 'remote')
        strip_tags = request.form.getlist('strip_tags')
        
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
            for url in target_urls:
                try:
                    res = scraper.scrape(url, dynamic=dynamic, svg_action=svg_action, image_action=image_action, strip=strip_tags)
                    results.append(res)
                except Exception as e:
                    error = f"Error scraping {url}: {e}"
                    # We continue with other URLs if one fails
            
    return render_template('index.html', urls_input=urls_input, dynamic=dynamic, svg_action=svg_action, image_action=image_action, strip_tags=strip_tags, results=results, error=error)

def create_app():
    return app

if __name__ == "__main__":
    # Use PORT from environment variable or default to 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
