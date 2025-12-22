from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

def create_app():
    return app

if __name__ == "__main__":
    app.run(debug=True)
