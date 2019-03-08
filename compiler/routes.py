"""Provides the main API blueprint for compilation."""

from typing import Callable, Union
from functools import wraps
from werkzeug.exceptions import Unauthorized, Forbidden, BadRequest
from flask.json import jsonify
from flask import Blueprint, current_app, redirect, request, g, Response, \
    send_file

from arxiv.users.auth.decorators import scoped
from arxiv.users.auth import scopes
from arxiv import status
from arxiv.base import logging
from arxiv.users.domain import Session, Scope
from arxiv.users.auth import scopes
from arxiv.users.auth.decorators import scoped

from . import controllers
from .domain import Task

logger = logging.getLogger(__name__)

blueprint = Blueprint('api', __name__, url_prefix='')

base_url = '/<string:source_id>/<string:checksum>/<string:output_format>'


def authorizer(scope: Scope) -> Callable[[Task], bool]:
    """Make an authorizer function for injection into a controller."""
    def inner(task: Task) -> bool:
        """Check whether the session is authorized for a specific resource."""
        # return True
        return (request.auth.is_authorized(scope, task.task_id)
                or (request.auth.user
                    and str(request.auth.user.user_id) == str(task.owner)))
    return inner


def resource_id(source_id, checksum, output_format) -> str:
    """Get the resource ID for an endpoint."""
    return f"{source_id}/{checksum}/{output_format}"


@blueprint.route('/status', methods=['GET'])
def get_service_status() -> Union[str, Response]:
    """Get information about the current status of compilation service."""
    return jsonify({'iam': 'ok'})


@blueprint.route('/', methods=['POST'])
@scoped(scopes.CREATE_COMPILE)
def compile() -> Response:
    """Request that a source package be compiled."""
    request_data = request.get_json(force=True)
    token = request.environ['token']
    logger.debug('Request for compilation: %s', request_data)
    logger.debug('Got token: %s', token)
    data, code, head = controllers.compile(request_data, token, request.auth,
                                           authorizer(scopes.CREATE_COMPILE))
    return jsonify(data), code, head


@blueprint.route(base_url, methods=['GET'])
@scoped(scopes.READ_COMPILE, resource=resource_id)
def get_status(source_id: str, checksum: int, output_format: str) -> Response:
    """Get the status of a compilation task."""
    data, code, head = controllers.get_status(source_id, checksum,
                                              output_format,
                                              authorizer(scopes.READ_COMPILE))
    if code in [status.HTTP_303_SEE_OTHER, status.HTTP_302_FOUND]:
        return redirect(head['Location'], code=code)
    return jsonify(data), code, head


@blueprint.route(f'{base_url}/log', methods=['GET'])
@scoped(scopes.READ_COMPILE, resource=resource_id)
def get_log(source_id: str, checksum: int, output_format: str) -> Response:
    """Get a compilation log."""
    resp = controllers.get_log(source_id, checksum, output_format,
                               authorizer(scopes.READ_COMPILE))
    data, status_code, headers = resp
    response = send_file(data['stream'], mimetype=data['content_type'],
                         attachment_filename=data['filename'])
    return response


@blueprint.route(f'{base_url}/product', methods=['GET'])
@scoped(scopes.READ_COMPILE, resource=resource_id)
def get_product(source_id: str, checksum: int, output_format: str) -> Response:
    """Get a compilation product."""
    data, code, head = controllers.get_product(source_id, checksum,
                                               output_format,
                                               authorizer(scopes.READ_COMPILE))
    response = send_file(data['stream'], mimetype=data['content_type'],
                         attachment_filename=data['filename'])
    response.set_etag(head.get('ETag'))
    return response
