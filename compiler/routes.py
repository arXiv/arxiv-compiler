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

from arxiv.submission.domain import User, Client, Classification
from . import controllers

logger = logging.getLogger(__name__)

blueprint = Blueprint('api', __name__, url_prefix='')


@blueprint.route('/status', methods=['GET'])
@scoped(scopes.CREATE_SUBMISSION)
def get_service_status() -> Union[str, Response]:
    """Get information about the current status of compilation service."""
    return jsonify({'iam': 'ok'})


@blueprint.route('/', methods=['POST'])
def request_compilation() -> Response:
    # data, status_code, headers =
    request_data = request.json(force=True)
    data, status_code, headers = controllers.request_compilation(request_data)
    return jsonify(data), status_data, headers


@blueprint.route('/<int:source_id>/<str:checksum>/<str:format>', methods=['GET'])
def get_compilation_info(source_id: int, checksum: int, format: str) -> Response:
    data, status_code, headers = controllers.get_compilation_info(source_id, checksum, format)
    return jsonify(data), status_code, headers


@blueprint.route('/<int:source_id>/<str:checksum>/<str:format>/log', methods=['GET'])
def get_compilation_log(source_id: int, checksum: int, format: str) -> Response:
    data, status_code, headers = controllers.get_compilation_log(source_id, checksum, format)
    return jsonify(data), status_code, headers


@blueprint.route('/<int:source_id>/<str:checksum>/<str:format>/product', methods=['GET'])
def get_compilation_product(source_id: int, checksum: int, format: str) -> Response:
    data, status_code, headers = controllers.get_compilation_product(source_id, checksum, format)
    response = send_file(data, mimetype="application/tar+gzip")
    response.set_etag(headers.get('ETag'))
    return response


@blueprint.route('/task/<string:task_id>', methods=['GET'])
def get_compilation_status(task_id: str) -> Response:
    data, status_code, headers = controllers.get_compilation_status(task_id)
    if status_code == status.HTTP_303_SEE_OTHER:
        return redirect(headers['Location'], status=status.HTTP_303_SEE_OTHER)
    return jsonify(data), status_code, headers
