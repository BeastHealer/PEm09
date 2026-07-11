"""
WSGI entry point for production deployment (Gunicorn, Docker).
"""

from main import init_rag
from bot import app

init_rag()
