"""Request controllers."""

from typing import Tuple, Optional, Callable, Any
from http import HTTPStatus as status

from werkzeug import MultiDict
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError, \
    Forbidden

from flask import url_for

from arxiv.users.domain import Session
from arxiv.base import logging

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


def _status_from_store(source_id: str, checksum: str,
                       output_format: Format) -> Optional[Task]:
    """Get a :class:`.Task` from storage."""
    store = Store.current_session()
    try:
        stat = store.get_status(source_id, checksum, output_format)
        logger.debug('Got status from store: %s', stat)
        return stat
    except DoesNotExist as e:
        logger.debug('No such compilation: %s', e)
    # except Exception as e:
    #     logger.debug('No such compilation: %s', e)
    return None


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
    if 'output_format' in request_data:
        requested_format = request_data['output_format']
        try:
            output_format = Format(requested_format)
        except ValueError as e:
            raise BadRequest(f'Unsupported format: {requested_format}') from e
    else:
        output_format = Format.PDF

    source_id = request_data.get('source_id', None)
    checksum = request_data.get('checksum', None)

    if source_id is None or not source_id.isdecimal():
        logger.debug('Missing or invalid source_id: %s', source_id)
        raise BadRequest(f'Missing or invalid source_id: {source_id}')
    if checksum is None or not is_urlsafe_base64(checksum):
        logger.debug('Not a valid source checksum: %s', checksum)
        raise BadRequest(f'Not a valid source checksum: {checksum}')

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
        info = _status_from_store(source_id, checksum, output_format)
        if info is not None:
            if not is_authorized(info):
                raise Forbidden('Not authorized to compile this resource')
            logger.debug('compilation exists, redirecting')
            return _redirect_to_status(source_id, checksum, output_format)

    owner = _get_owner(source_id, checksum, token)
    try:
        compiler.start_compilation(source_id, checksum, stamp_label,
                                   stamp_link, output_format, token=token,
                                   owner=owner)
    except compiler.TaskCreationFailed as e:
        logger.error('Failed to start compilation: %s', e)
        raise InternalServerError('Failed to start compilation') from e
    return _redirect_to_status(source_id, checksum, output_format,
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
    if not source_id.isdecimal():
        raise BadRequest(f'Invalid source_id: {source_id}')
    try:
        product_format = Format(output_format)
    except ValueError as e:
        raise BadRequest(f'Unsupported format: {output_format}') from e
    logger.debug('get_status for %s, %s, %s', source_id, checksum,
                 output_format)
    info = _status_from_store(source_id, checksum, product_format)
    # Verify that the requester is authorized to view this resource.
    if info is None:
        raise NotFound('No such resource')
    if not is_authorized(info):
        raise Forbidden('Access denied')
    return info.to_dict(), status.OK, {'ARXIV-OWNER': info.owner}


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
    if not source_id.isdecimal():
        raise BadRequest(f'Invalid source_id: {source_id}')
    store = Store.current_session()
    try:
        product_format = Format(output_format)
    except ValueError as e:
        raise BadRequest(f'Unsupported format: {output_format}') from e

    # Verify that the requester is authorized to view this resource.
    info = _status_from_store(source_id, checksum, product_format)
    if info is None:
        raise NotFound('No such resource')
    if not is_authorized(info):
        raise Forbidden('Access denied')

    try:
        product = store.retrieve(source_id, checksum, product_format)
    except DoesNotExist as e:
        raise NotFound('No such compilation product') from e
    data = {
        'stream': product.stream,
        'content_type': product_format.content_type,
        'filename': f'{source_id}.{product_format.ext}',
    }
    headers = {'ARXIV-OWNER': info.owner, 'ETag': product.checksum}
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
    store = Store.current_session()
    try:
        product_format = Format(output_format)
    except ValueError as e:
        raise BadRequest(f'Unsupported format: {output_format}') from e
    if not source_id.isdecimal():
        raise BadRequest(f'Invalid source_id: {source_id}')

    # Verify that the requester is authorized to view this resource.
    info = _status_from_store(source_id, checksum, product_format)
    if info is None:
        raise NotFound('No such resource')
    if not is_authorized(info):
        raise Forbidden('Access denied')

    try:
        product = store.retrieve_log(source_id, checksum, product_format)
    except DoesNotExist as e:
        raise NotFound('No such compilation product') from e
    data = {
        'stream': product.stream,
        'content_type': 'text/plain',
        'filename': f'{source_id}.{product_format.ext}'
    }
    headers = {'ARXIV-OWNER': info.owner, 'ETag': product.checksum}
    return data, status.OK, headers


def _get_owner(source_id: str, checksum: str, token: str) -> Optional[str]:
    """Get the owner of the upload source package."""
    fm = filemanager.FileManager.current_session()
    try:
        logger.debug('Check for source')
        try:
            owner: Optional[str] = fm.owner(source_id, checksum, token)
        except Exception as e:
            logger.debug('No such source')
            raise NotFound('No such source') from e
    except (filemanager.exceptions.RequestForbidden,
            filemanager.exceptions.RequestUnauthorized):
        logger.debug('Not authorized to check source')
        raise Forbidden('Not authorized to access source')
    return owner
