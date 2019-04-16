"""Web Server Gateway Interface entry-point."""

from compiler.factory import create_app
import os


__flask_app__ = create_app()


def application(environ, start_response):
    """WSGI application factory."""
    for key, value in environ.items():
        os.environ[key] = str(value)
    return __flask_app__(environ, start_response)
