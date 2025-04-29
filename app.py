from flask import Flask, render_template
from flask_cors import CORS
from resume_bp import resume_bp
from rubric_bp import rubric_bp

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Register blueprints
app.register_blueprint(resume_bp)
app.register_blueprint(rubric_bp)

# Root route
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)