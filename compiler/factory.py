"""Application factory for compiler service."""

import logging

from flask import Flask

from arxiv.base import Base
from arxiv.users import auth
from arxiv.base.middleware import wrap, request_logs

from .services import filemanager
from . import routes


def create_web_app() -> Flask:
    """Create an instance of the compiler service app."""
    app = Flask(__name__)
    filemanager.init_app(app)
    app.config.from_pyfile('config.py')

    Base(app)
    auth.Auth(app)

    # Don't forget to register your API blueprint, when it's ready.
    app.register_blueprint(routes.blueprint)

    wrap(app, [auth.middleware.AuthMiddleware])

    return app
