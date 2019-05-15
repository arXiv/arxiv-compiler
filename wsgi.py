"""Web Server Gateway Interface entry-point."""

import os
from typing import Optional
from flask import Flask
from compiler.factory import create_app

__flask_app__ = create_app()


def application(environ, start_response):
    """WSGI application factory."""
    global __flask_app__
    for key, value in environ.items():
        os.environ[key] = str(value)

        # The value for SERVER_NAME will usually be the container ID or some
        # other useless hostname.
        if key in __flask_app__.config and key != 'SERVER_NAME':
            __flask_app__.config[key] = value

    return __flask_app__(environ, start_response)
