from flask import Flask, render_template, request, jsonify
import os
from md_scraper.scraper import Scraper

app = Flask(__name__)

@app.route('/api/scrape', methods=['POST'])
def api_scrape():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required'}), 400

    url = data['url']
    dynamic = data.get('dynamic', False)
    svg_action = data.get('svg_action', 'image')
    strip_tags = data.get('strip_tags', [])

    scraper = Scraper()
    try:
        result = scraper.scrape(url, dynamic=dynamic, svg_action=svg_action, strip=strip_tags)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/', methods=['GET', 'POST'])
def index():
    url = None
    dynamic = False
    svg_action = 'image'
    strip_tags = []
    result = None
    error = None
    
    if request.method == 'POST':
        url = request.form.get('url')
        dynamic = 'dynamic' in request.form
        svg_action = request.form.get('svg_action', 'image')
        strip_tags = request.form.getlist('strip_tags')
        
        scraper = Scraper()
        try:
            result = scraper.scrape(url, dynamic=dynamic, svg_action=svg_action, strip=strip_tags)
        except Exception as e:
            error = f"Error scraping {url}: {e}"
            
    return render_template('index.html', url=url, dynamic=dynamic, svg_action=svg_action, strip_tags=strip_tags, result=result, error=error)

def create_app():
    return app

if __name__ == "__main__":
    # Use PORT from environment variable or default to 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
