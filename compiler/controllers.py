"""Request controllers."""

import string
from typing import Tuple, Optional, Callable, Any
from http import HTTPStatus as status
from base64 import urlsafe_b64encode

from werkzeug import MultiDict
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError, \
    Forbidden

from flask import url_for

from arxiv.users.domain import Session
from arxiv.base import logging
from arxiv.base.globals import get_application_config

from .services import Store, filemanager
from .services.store import DoesNotExist
from . import compiler
from .domain import Task, Product, Status, Format

logger = logging.getLogger(__name__)

Response = Tuple[dict, int, dict]

urlsafe_base64_alphabet = (set(range(65, 91))         # A-Z
                           | set(range(97, 123))      # a-z
                           | set(range(48, 58))       # 0-9
                           | set((45, 95, 61)))       # -_=
"""
Ordinal representation of the URL-safe Base64 alphabet.

RFC 3548 `defines <https://tools.ietf.org/html/rfc3548.html#page-5>`_ the
base 64 alphabet as ``A-Za-z0-9+/=``. The Python base64 module `describes
<https://docs.python.org/3/library/base64.html#base64.urlsafe_b64encode>`_
the URL-safe alphabet as the standard Base64 alphabet with ``-``
substituted for ``+`` and ``_`` substituted for ``/``.
"""


def is_urlsafe_base64(val: str) -> bool:
    """
    Determine whether a string is exclusively from the urlsafe base64 alphabet.

    See :const:`.urlsafe_base64_alphabet`.
    """
    return bool(len(set((ord(c) for c in val)) - urlsafe_base64_alphabet) == 0)


def _redirect_to_status(source_id: str, checksum: str, output_format: Format,
                        code: int = status.SEE_OTHER) -> Response:
    """Redirect to the status endpoint."""
    location = url_for('api.get_status', source_id=source_id,
                       checksum=checksum, output_format=output_format.value)
    return {}, code, {'Location': location}


def service_status(*args: Any, **kwargs: Any) -> Response:
    """Exercise dependencies and verify operational status."""
    fm = filemanager.FileManager.current_session()
    store = Store.current_session()
    response_data = {}
    response_data['store'] = store.is_available()
    response_data['compiler'] = compiler.is_available()
    response_data['filemanager'] = fm.is_available()
    if not all(response_data.values()):
        return response_data, status.SERVICE_UNAVAILABLE, {}
    return response_data, status.OK, {}


def compile(request_data: MultiDict, token: str, session: Session,
            is_authorized: Callable = lambda task: True) -> Response:
    """
    Start compilation of an upload workspace.

    Parameters
    ----------
    request_data : :class:`.MultiDict`
        Data payload from the request.
    token : str
        Auth token to be used for subrequests (e.g. to file management
        service).

    Returns
    -------
    dict
        Response data.
    int
        HTTP status code.
    dict
        Headers to add to response.

    """
    # Since these may originate from a JSON payload, values may be deserialized
    # as int; cast to str to ensure that we are passing the correct type.
    source_id = _validate_source_id(str(request_data.get('source_id', '')))
    checksum = _validate_checksum(str(request_data.get('checksum', '')))
    product_format = _validate_output_format(
        request_data.get('output_format', Format.PDF.value))

    # We don't want to compile the same source package twice.
    force = request_data.get('force', False)

    # Support label and link for PS/PDF Stamping
    # Test
    stamp_label: Optional[str] = request_data.get('stamp_label', None)
    stamp_link: Optional[str] = request_data.get('stamp_link', None)

    logger.debug('%s: request compilation with %s', __name__, request_data)

    # Unless we are forcing recompilation, we do not want to compile the same
    # source twice. So we check our storage for a compilation (successful or
    # not) corresponding to the requested source package.
    if not force:
        try:
            task_state = compiler.get_task(source_id, checksum, product_format)
            if not is_authorized(task_state):
                raise Forbidden('Not authorized to compile this resource')
            logger.debug('compilation exists, redirecting')
            return _redirect_to_status(source_id, checksum, product_format)
        except compiler.NoSuchTask as e:
            # raise NotFound('No such task') from e
            pass

    owner = _get_owner(source_id, checksum, token)
    try:
        compiler.start_compilation(source_id, checksum, stamp_label,
                                   stamp_link, product_format, token=token,
                                   owner=owner)
    except compiler.TaskCreationFailed as e:
        logger.error('Failed to start compilation: %s', e)
        raise InternalServerError('Failed to start compilation') from e
    return _redirect_to_status(source_id, checksum, product_format,
                               status.ACCEPTED)


def get_status(source_id: str, checksum: str, output_format: str,
               is_authorized: Callable = lambda task: True) -> Response:
    """
    Get the status of a compilation.

    See ``schema/resources/compilationStatus.json``.

    Parameters
    ----------
    source_id : int
        Identifier for the source package.
    checksum : str
        Checksum of the source package to compile.
    output_format : str
        Desired output format. Only `pdf` is currently supported.

    Returns
    -------
    dict
        Response data.
    int
        HTTP status code.
    dict
        Headers to add to response.

    """
    source_id = _validate_source_id(source_id)
    checksum = _validate_checksum(checksum)
    product_format = _validate_output_format(output_format)

    logger.debug('get_status for %s, %s, %s', source_id, checksum,
                 output_format)
    try:
        task_state = compiler.get_task(source_id, checksum, product_format)
    except compiler.NoSuchTask as e:
        raise NotFound('No such compilation task') from e

    # Verify that the requester is authorized to view this resource.
    if not is_authorized(task_state):
        raise Forbidden('Access denied')
    return task_state.to_dict(), status.OK, {'ARXIV-OWNER': task_state.owner}


def get_product(source_id: str, checksum: str, output_format: str,
                is_authorized: Callable = lambda task: True) -> Response:
    """
    Get the product of a compilation.

    Parameters
    ----------
    source_id : int
        Identifier for the source package.
    checksum : str
        Checksum of the source package to compile.
    output_format : str
        Desired output format. Only `pdf` is currently supported.

    Returns
    -------
    dict
        Response data.
    int
        HTTP status code.
    dict
        Headers to add to response.

    """
    source_id = _validate_source_id(source_id)
    checksum = _validate_checksum(checksum)
    product_format = _validate_output_format(output_format)

    # Verify that the requester is authorized to view this resource.
    try:
        task_state = compiler.get_task(source_id, checksum, product_format)
    except compiler.NoSuchTask as e:
        raise NotFound('No such task') from e
    if not is_authorized(task_state):
        raise Forbidden('Access denied')

    store = Store.current_session()
    try:
        product = store.retrieve(source_id, checksum, product_format)
    except DoesNotExist as e:
        raise NotFound('No such compilation product') from e
    data = {
        'stream': product.stream,
        'content_type': product_format.content_type,
        'filename': f'{source_id}.{product_format.ext}',
    }
    headers = {'ARXIV-OWNER': task_state.owner, 'ETag': product.checksum}
    return data, status.OK, headers


def get_log(source_id: str, checksum: str, output_format: str,
            is_authorized: Callable = lambda task: True) -> Response:
    """
    Get a compilation log.

    Parameters
    ----------
    source_id : int
        Identifier for the source package.
    checksum : str
        Checksum of the source package to compile.
    output_format : str
        Desired output format. Only `pdf` is currently supported.

    Returns
    -------
    dict
        Response data.
    int
        HTTP status code.
    dict
        Headers to add to response.

    """
    source_id = _validate_source_id(source_id)
    checksum = _validate_checksum(checksum)
    product_format = _validate_output_format(output_format)

    # Verify that the requester is authorized to view this resource.
    try:
        task_state = compiler.get_task(source_id, checksum, product_format)
    except compiler.NoSuchTask as e:
        raise NotFound('No such task') from e
    if not is_authorized(task_state):
        raise Forbidden('Access denied')

    store = Store.current_session()
    try:
        product = store.retrieve_log(source_id, checksum, product_format)
    except DoesNotExist as e:
        raise NotFound('No such compilation product') from e
    data = {
        'stream': product.stream,
        'content_type': 'text/plain',
        'filename': f'{source_id}.{product_format.ext}'
    }
    headers = {'ARXIV-OWNER': task_state.owner, 'ETag': product.checksum}
    return data, status.OK, headers


def _validate_source_id(source_id: str) -> str:
    if not source_id or not _is_valid_source_id(source_id):
        raise BadRequest(f'Invalid source_id: {source_id}')
    return source_id


def _validate_checksum(checksum: str) -> str:
    verify = get_application_config().get('FILEMANAGER_VERIFY_CHECKSUM', True)
    if not checksum or not is_urlsafe_base64(checksum):
        # If we are not verifying the checksum, attempt to create a URL-safe
        # value that we can use to identify the source package for our own
        # purposes.
        if checksum and not verify:
            try:
                checksum_bytes = urlsafe_b64encode(checksum.encode('utf-8'))
                return checksum_bytes.decode('utf-8')
            except UnicodeDecodeError:
                pass
        logger.debug('Not a valid source checksum: %s', checksum)
        raise BadRequest(f'Not a valid source checksum: {checksum}')
    return checksum


def _validate_output_format(output_format: str) -> Format:
    try:
        return Format(output_format)
    except ValueError as e:
        raise BadRequest(f'Unsupported format: {output_format}') from e


def _is_valid_source_id(source_id: str) -> bool:
    allowed = set(string.ascii_letters) | set(string.digits) | set('.-_')
    return bool(len(set(source_id) - allowed) == 0)


def _get_owner(source_id: str, checksum: str, token: str) -> Optional[str]:
    """Get the owner of the upload source package."""
    fm = filemanager.FileManager.current_session()
    try:
        logger.debug('Check for source')
        try:
            owner: Optional[str] = fm.owner(source_id, checksum, token)
        except Exception as e:
            raise NotFound('No such source') from e
    except (filemanager.exceptions.RequestForbidden,
            filemanager.exceptions.RequestUnauthorized):
        logger.debug('Not authorized to check source')
        raise Forbidden('Not authorized to access source')
    return owner
