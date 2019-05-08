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
        output_format = Format(request_data['output_format'])
    else:
        output_format = Format.PDF
    source_id = request_data.get('source_id', None)
    checksum = request_data.get('checksum', None)
    if source_id is None:
        logger.debug('Missing required parameter: source_id')
        raise BadRequest('Missing required parameter: source_id')
    if checksum is None:
        logger.debug('Missing required parameter: checksum')
        raise BadRequest('Missing required parameter: checksum')

    # We don't want to compile the same source package twice.
    force = request_data.get('force', False)

    # Support label and link for PS/PDF Stamping
    # Test
    stamp_label: Optional[str] = request_data.get('stamp_label', None)
    stamp_link: Optional[str] = request_data.get('stamp_link', None)

    logger.debug('%s: request compilation with %s', __name__, request_data)
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
    try:
        product_format = Format(output_format)
    except ValueError:
        raise BadRequest('Invalid format')
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
    store = Store.current_session()
    try:
        product_format = Format(output_format)
    except ValueError:  # Not a valid format.
        raise BadRequest('Invalid format')

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
    except ValueError:  # Not a valid format.
        raise BadRequest('Invalid format')

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
