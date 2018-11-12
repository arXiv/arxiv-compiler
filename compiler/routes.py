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

from . import controllers

logger = logging.getLogger(__name__)

blueprint = Blueprint('api', __name__, url_prefix='')


@blueprint.route('/status', methods=['GET'])
def get_service_status() -> Union[str, Response]:
    """Get information about the current status of compilation service."""
    return jsonify({'iam': 'ok'})


@blueprint.route('/', methods=['POST'])
def request_compilation() -> Response:
    """Request that a source package be compiled."""
    # data, status_code, headers =
    request_data = request.get_json(force=True)
    data, status_code, headers = controllers.request_compilation(request_data)
    return jsonify(data), status_code, headers


@blueprint.route(
    '/<string:source_id>/<string:checksum>/<string:output_format>',
    methods=['GET']
)
def get_info(source_id: str, checksum: int, output_format: str) \
        -> Response:
    """Get information about a compilation."""
    resp = controllers.get_info(source_id, checksum, output_format)
    data, status_code, headers = resp
    if status_code in [status.HTTP_303_SEE_OTHER, status.HTTP_302_FOUND]:
        return redirect(headers['Location'], code=status_code)
    return jsonify(data), status_code, headers


@blueprint.route(
    '/<string:source_id>/<string:checksum>/<string:output_format>/log',
    methods=['GET']
)
def get_log(source_id: str, checksum: int, output_format: str) -> Response:
    """Get a compilation log."""
    resp = controllers.get_log(source_id, checksum, output_format)
    data, status_code, headers = resp
    response = send_file(data, mimetype="text/plain")
    return response


@blueprint.route(
    '/<string:source_id>/<string:checksum>/<string:output_format>/product',
    methods=['GET']
)
def get_product(source_id: str, checksum: int, output_format: str) -> Response:
    """Get a compilation product."""
    resp = controllers.get_product(source_id, checksum, output_format)
    data, status_code, headers = resp
    response = send_file(data, mimetype="application/tar+gzip")
    response.set_etag(headers.get('ETag'))
    return response


@blueprint.route('/task/<string:task_id>', methods=['GET'])
def get_status(task_id: str) -> Response:
    """Get the status of a compilation task."""
    data, status_code, headers = controllers.get_status(task_id)
    if status_code in [status.HTTP_303_SEE_OTHER, status.HTTP_302_FOUND]:
        return redirect(headers['Location'], code=status_code)
    return jsonify(data), status_code, headers
