from flask import Flask, render_template, request
import os
from md_scraper.scraper import Scraper

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    url = None
    dynamic = False
    svg_action = 'image'
    result = None
    error = None
    
    if request.method == 'POST':
        url = request.form.get('url')
        dynamic = 'dynamic' in request.form
        svg_action = request.form.get('svg_action', 'image')
        
        scraper = Scraper()
        try:
            result = scraper.scrape(url, dynamic=dynamic, svg_action=svg_action)
        except Exception as e:
            error = f"Error scraping {url}: {e}"
            
    return render_template('index.html', url=url, dynamic=dynamic, svg_action=svg_action, result=result, error=error)

def create_app():
    return app

if __name__ == "__main__":
    # Use PORT from environment variable or default to 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
