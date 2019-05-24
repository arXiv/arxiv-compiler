"""Application factory for compiler service."""
import os
import time

from typing import Any
from typing_extensions import Protocol

from werkzeug.exceptions import Forbidden, Unauthorized, NotFound, \
    InternalServerError, BadRequest, HTTPException, MethodNotAllowed
from werkzeug.contrib.profiler import ProfilerMiddleware

from flask import Flask, jsonify, Response

from arxiv.base import Base, logging
from arxiv.users import auth
from arxiv.base.middleware import wrap, request_logs
from arxiv import vault

from .celery import celery_app
from .services import store, filemanager
from . import routes, compiler


logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create an instance of the compiler service app."""
    from . import celeryconfig
    app = Flask(__name__)
    filemanager.FileManager.init_app(app)
    store.Store.init_app(app)
    app.config.from_pyfile('config.py')
    celery_app.config_from_object(celeryconfig)

    Base(app)
    auth.Auth(app)

    app.register_blueprint(routes.blueprint)
    register_error_handlers(app)

    middleware = [auth.middleware.AuthMiddleware]

    if app.config['VAULT_ENABLED']:
        middleware.insert(0, vault.middleware.VaultMiddleware)
    wrap(app, middleware)
    if app.config['VAULT_ENABLED']:
        app.middlewares['VaultMiddleware'].update_secrets({})

    # Leaving this here for future performance tuning. - Erick
    #
    # app.config['PROFILE'] = True
    # app.config['DEBUG'] = True
    # app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[100],
    #                                   sort_by=('cumtime', ))
    #

    if app.config['WAIT_FOR_SERVICES']:
        with app.app_context():
            logger.info('initialize and wait for upstream services')
            # Adding a wait here can help keep boto3 from getting stuck if
            # we are starting localstack at the same time. This can probably
            # just be 0 (default) in production.
            time.sleep(app.config['WAIT_ON_STARTUP'])
            filemanager_service = filemanager.FileManager.current_session()
            store_service = store.Store.current_session()
            store_service.initialize()
            wait_for(filemanager_service)
            wait_for(compiler, await_result=True)

        logger.info('All upstream services are available; ready to start')

    return app


def create_worker_app() -> Flask:
    """Create an instance of the compiler worker app."""
    from . import celeryconfig
    app = Flask(__name__)
    celery_app.config_from_object(celeryconfig)
    filemanager.FileManager.init_app(app)
    store.Store.init_app(app)
    app.config.from_pyfile('config.py')

    Base(app)
    auth.Auth(app)

    app.register_blueprint(routes.blueprint)
    # Leaving this here for future performance tuning. - Erick
    #
    # app.config['PROFILE'] = True
    # app.config['DEBUG'] = True
    # app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[100],
    #                                   sort_by=('cumtime', ))
    #

    if app.config['WAIT_FOR_SERVICES']:
        with app.app_context():
            logger.info('initialize and wait for upstream services')
            # Adding a wait here can help keep boto3 from getting stuck if
            # we are starting localstack at the same time. This can probably
            # just be 0 (default) in production.
            time.sleep(app.config['WAIT_ON_STARTUP'])
            filemanager_service = filemanager.FileManager.current_session()
            store_service = store.Store.current_session()
            store_service.initialize()
            wait_for(filemanager_service)

        logger.info('All upstream services are available; ready to start')

    return app


class IAwaitable(Protocol):
    """An object that provides an ``is_available`` predicate."""

    def is_available(self, **kwargs: Any) -> bool:
        """Check whether an object (e.g. a service) is available."""
        ...


def wait_for(service: IAwaitable, delay: int = 2, **extra: Any) -> None:
    """Wait for a service to become available."""
    if hasattr(service, '__name__'):
        service_name = service.__name__
    elif hasattr(service, '__class__'):
        service_name = service.__class__.__name__
    else:
        service_name = str(service)

    logger.info('await %s', service_name)
    while not service.is_available(**extra):
        logger.info('service %s is not available; try again', service_name)
        time.sleep(delay)
    logger.info('service %s is available!', service_name)


def register_error_handlers(app: Flask) -> None:
    """Register error handlers for the Flask app."""
    app.errorhandler(Forbidden)(jsonify_exception)
    app.errorhandler(Unauthorized)(jsonify_exception)
    app.errorhandler(BadRequest)(jsonify_exception)
    app.errorhandler(InternalServerError)(jsonify_exception)
    app.errorhandler(NotFound)(jsonify_exception)
    app.errorhandler(MethodNotAllowed)(jsonify_exception)


def jsonify_exception(error: HTTPException) -> Response:
    """Render exceptions as JSON."""
    exc_resp = error.get_response()
    response: Response = jsonify(reason=error.description)
    response.status_code = exc_resp.status_code
    return response
