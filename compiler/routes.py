"""
Provides the main API blueprint for compilation.

Notes
-----
mypy doesn't have types for flask.Headers.extend, so those lines are
excluded from type checking.

"""

from typing import Callable, Union, Iterable, Tuple, Optional
from functools import wraps
from http import HTTPStatus as status
from werkzeug.exceptions import Unauthorized, Forbidden, BadRequest
from werkzeug.wrappers import Response as WkzResponse
from flask.json import jsonify
from flask import Blueprint, current_app, redirect, request, g, send_file
from flask import Response as FlaskResponse

from arxiv.users.auth.decorators import scoped
from arxiv.users.auth import scopes
from arxiv.base import logging
from arxiv.users.domain import Session, Scope
from arxiv.users.auth import scopes
from arxiv.users.auth.decorators import scoped

from . import controllers
from .domain import Task

Response = Union[FlaskResponse, WkzResponse]

logger = logging.getLogger(__name__)

blueprint = Blueprint('api', __name__, url_prefix='')

base_url = '/<string:source_id>/<string:checksum>/<string:output_format>'


def authorizer(scope: Scope) -> Callable[[Task], bool]:
    """Make an authorizer function for injection into a controller."""
    def inner(task: Task) -> bool:
        """Check whether the session is authorized for a specific resource."""
        if not task.owner:  # If there is no owner, this is a public resource.
            return True
        return (request.auth.is_authorized(scope, task.task_id)
                or (request.auth.user
                    and str(request.auth.user.user_id) == str(task.owner)))
    return inner


def resource_id(source_id: str, checksum: str, output_format: str) -> str:
    """Get the resource ID for an endpoint."""
    return f"{source_id}/{checksum}/{output_format}"


@blueprint.route('/status', methods=['GET'])
def get_service_status() -> Union[str, Response]:
    """Get information about the current status of compilation service."""
    data, code, headers = controllers.service_status()
    response: Response = jsonify(data)
    response.status_code = code
    response.headers.extend(headers.items())    # type: ignore
    return response


@blueprint.route('/', methods=['POST'])
@scoped(scopes.CREATE_COMPILE)
def compile() -> Response:
    """Request that a source package be compiled."""
    request_data = request.get_json(force=True)
    token = request.environ['token']
    logger.debug('Request for compilation: %s', request_data)
    logger.debug('Got token: %s', token)
    data, code, headers = controllers.compile(
        request_data,
        token,
        request.auth,
        authorizer(scopes.CREATE_COMPILE)
    )
    response: Response = jsonify(data)
    response.status_code = code
    response.headers.extend(headers.items())    # type: ignore
    return response


@blueprint.route(base_url, methods=['GET'])
@scoped(scopes.READ_COMPILE, resource=resource_id)
def get_status(source_id: str, checksum: str, output_format: str) -> Response:
    """Get the status of a compilation task."""
    data, code, headers = controllers.get_status(
        source_id,
        checksum,
        output_format,
        authorizer(scopes.READ_COMPILE)
    )
    if code in [status.SEE_OTHER, status.FOUND]:
        return redirect(headers['Location'], code=code)
    response: Response = jsonify(data)
    response.status_code = code
    response.headers.extend(headers.items())    # type: ignore
    return response


@blueprint.route(f'{base_url}/log', methods=['GET'])
@scoped(scopes.READ_COMPILE, resource=resource_id)
def get_log(source_id: str, checksum: str, output_format: str) -> Response:
    """Get a compilation log."""
    resp = controllers.get_log(source_id, checksum, output_format,
                               authorizer(scopes.READ_COMPILE))
    data, status_code, headers = resp
    response: Response = send_file(data['stream'],
                                   mimetype=data['content_type'],
                                   attachment_filename=data['filename'])
    return response


@blueprint.route(f'{base_url}/product', methods=['GET'])
@scoped(scopes.READ_COMPILE, resource=resource_id)
def get_product(source_id: str, checksum: str, output_format: str) -> Response:
    """Get a compilation product."""
    data, code, head = controllers.get_product(source_id, checksum,
                                               output_format,
                                               authorizer(scopes.READ_COMPILE))
    response: Response = send_file(data['stream'],
                                   mimetype=data['content_type'],
                                   attachment_filename=data['filename'])
    response.set_etag(head.get('ETag'))
    return response
