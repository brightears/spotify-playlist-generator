#!/usr/bin/env python3
"""Simple test server to verify the new design works."""

from flask import Flask, render_template
import os
import sys

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, template_folder="templates")
app.config['SECRET_KEY'] = 'test-key-for-development'

# Mock user class for template
class MockUser:
    def __init__(self):
        self.is_authenticated = False
        self.email = "test@example.com"

# Create mock current_user
@app.context_processor
def inject_user():
    return dict(current_user=MockUser())

@app.route('/')
def index():
    """Test route for the new design."""
    return render_template('index.html')

@app.route('/test')
def test():
    """Simple test route."""
    return """
    <h1>Flask Test Server is Working!</h1>
    <p>Your server is running correctly.</p>
    <p><a href="/">View New Design</a></p>
    """

if __name__ == '__main__':
    print("🚀 Starting test server...")
    print("📱 Open http://localhost:3000 to see your new design")
    print("🔧 Test route: http://localhost:3000/test")
    app.run(host='0.0.0.0', port=3000, debug=True, use_reloader=False)