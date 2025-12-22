from flask import Flask, render_template, request
from md_scraper.scraper import Scraper

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    url = None
    dynamic = False
    result = None
    error = None
    
    if request.method == 'POST':
        url = request.form.get('url')
        dynamic = 'dynamic' in request.form
        
        scraper = Scraper()
        try:
            result = scraper.scrape(url, dynamic=dynamic)
        except Exception as e:
            error = f"Error scraping {url}: {e}"
            
    return render_template('index.html', url=url, dynamic=dynamic, result=result, error=error)

def create_app():
    return app

if __name__ == "__main__":
    app.run(debug=True)
