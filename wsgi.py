"""Web Server Gateway Interface entry-point."""

from compiler.factory import create_app
import os


def application(environ, start_response):
    """WSGI application factory."""
    for key, value in environ.items():
        os.environ[key] = str(value)
    app = create_app()
    return app(environ, start_response)
