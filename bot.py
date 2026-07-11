"""
Flask Application.
Initializes and configures the web application.
"""

from flask import Flask

from config import SECRET_KEY
from utils.logging import logger


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.secret_key = SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

    from handlers.routes import bp
    app.register_blueprint(bp)

    logger.info("Flask application created")
    return app


app = create_app()
