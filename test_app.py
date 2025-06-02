"""
Basic tests for the Spotify Playlist Generator application.
"""
import pytest
from app import create_app
from models import db, User
from flask_login import current_user

@pytest.fixture
def app():
    """Create and configure a Flask app for testing."""
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "SERVER_NAME": "localhost.localdomain",
    })
    
    # Create the database and tables
    with app.app_context():
        db.create_all()
        
        # Create a test user
        if not User.query.filter_by(email="test@example.com").first():
            user = User(email="test@example.com")
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
    
    yield app
    
    # Clean up
    with app.app_context():
        db.drop_all()

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """A test CLI runner for the app."""
    return app.test_cli_runner()

def test_home_page(client):
    """Test that the home page loads."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Spotify Playlist Generator' in response.data

def test_login_page(client):
    """Test that the login page loads."""
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert b'Log In' in response.data

def test_login(client):
    """Test user login."""
    response = client.post('/auth/login', data={
        'email': 'test@example.com',
        'password': 'password123',
        'remember': False
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Dashboard' in response.data

def test_test_session_route(client):
    """Test the test_session route."""
    response = client.get('/test-session')
    assert response.status_code == 200
    assert b'Session Information' in response.data