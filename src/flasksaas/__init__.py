"""FlaskSaaS-inspired skeleton package.
Contains auth + billing blueprints. This is just the minimal scaffold; we will
port over specific views and models incrementally.
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail

# Extension singletons (shared across modules)
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()

# ---------------------------------------------------------------------------
# Factory helper (for isolated testing)
# ---------------------------------------------------------------------------

def create_flasksaas_app(config_object: str | None = None) -> Flask:
    app = Flask(__name__, 
              instance_relative_config=True)

    # Handle database URL - Render uses 'postgres://' but SQLAlchemy needs 'postgresql://'
    import os
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    # defaults so the app can boot without env vars
    app.config.update(
        SECRET_KEY=os.environ.get('FLASK_SECRET_KEY', 'change-me'),
        SQLALCHEMY_DATABASE_URI=database_url or "sqlite:///instance/flasksaas.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        
        # Mail configuration
        MAIL_SERVER=os.environ.get('MAIL_SERVER', 'smtp.gmail.com'),
        MAIL_PORT=int(os.environ.get('MAIL_PORT', 587)),
        MAIL_USE_TLS=os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true',
        MAIL_USE_SSL=os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true',
        MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
        MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
        MAIL_DEFAULT_SENDER=os.environ.get('MAIL_DEFAULT_SENDER', 'support@brightears.io'),
    )

    if config_object:
        app.config.from_object(config_object)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    mail.init_app(app)

    # late imports to avoid circular deps
    from .auth.routes import auth_bp
    from .billing.routes import billing_bp, init_stripe
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(billing_bp, url_prefix="/billing")
    
    # Initialize Stripe when the app is created
    with app.app_context():
        init_stripe()

    return app


# user_loader to satisfy Flask-Login
@login_manager.user_loader
def _load_user(user_id):
    from .models import User  # local import
    return User.query.get(user_id)
