"""Request controllers."""

from typing import Tuple, Optional

from werkzeug import MultiDict
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError

from flask import url_for

from arxiv import status
from arxiv.base import logging

from .services import store
from . import compiler
from .domain import CompilationStatus, CompilationProduct, Status, Format

logger = logging.getLogger(__name__)

Response = Tuple[dict, int, dict]


def _status_from_store(source_id: str, checksum: str,
                       output_format: Format) -> Optional[CompilationStatus]:
    """Get a :class:`.CompilationStatus` from storage."""
    try:
        stat = store.get_status(source_id, checksum, output_format)
        logger.debug('Got status from store: %s', stat)
        return stat
    except store.DoesNotExist as e:
        logger.debug('No such compilation: %s', e)
    except Exception as e:
        logger.debug('No such compilation: %s', e)
    return None


def _status_from_task(source_id: str, checksum: str,
                      output_format: Format) -> Optional[CompilationStatus]:
    """Get a :class:`.CompilationStatus` from the task queue."""
    try:
        stat = compiler.get_task(source_id, checksum, output_format)
        logger.debug('Got status from previous task: %s', stat)
        return stat
    except compiler.NoSuchTask as e:
        logger.debug('No such compilation task: %s', e)
    return None


def _redirect_to_status(source_id: str, checksum: str, output_format: Format,
                        code: int = status.HTTP_303_SEE_OTHER) -> Response:
    """Redirect to the status endpoint."""
    location = url_for('api.get_status', source_id=source_id,
                       checksum=checksum, output_format=output_format.value)
    return {}, code, {'Location': location}


def compile(request_data: MultiDict, token: str) -> Response:
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

    force = request_data.get('force', False)
    logger.debug('%s: request compilation with %s', __name__, request_data)
    if not force:
        if _status_from_store(source_id, checksum, output_format) is not None:
            logger.debug('compilation exists, redirecting')
            return _redirect_to_status(source_id, checksum, output_format)
        if _status_from_task(source_id, checksum, output_format) is not None:
            logger.debug('compilation exists, redirecting')
            return _redirect_to_status(source_id, checksum, output_format)
    try:
        compiler.start_compilation(source_id, checksum, output_format,
                                   token=token)
    except compiler.TaskCreationFailed as e:
        logger.error('Failed to start compilation: %s', e)
        raise InternalServerError('Failed to start compilation') from e
    return _redirect_to_status(source_id, checksum, output_format,
                               status.HTTP_202_ACCEPTED)


def get_status(source_id: str, checksum: str, output_format: str) -> Response:
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
    if info is None:
        info = _status_from_task(source_id, checksum, product_format)
    if info is None:
        raise NotFound('No such compilation')
    return info.to_dict(), status.HTTP_200_OK, {}


def get_product(source_id: int, checksum: str, output_format: str) -> Response:
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
    try:
        product_format = Format(output_format)
    except ValueError:  # Not a valid format.
        raise BadRequest('Invalid format')
    try:
        product = store.retrieve(source_id, checksum, product_format)
    except store.DoesNotExist as e:
        raise NotFound('No such compilation product') from e
    except Exception as e:
        logger.error('Unhandled exception: %s', e)
        raise InternalServerError('Unhandled exception: %s' % e)
    data = {
        'stream': product.stream,
        'content_type': product_format.content_type,
        'filename': f'{source_id}.{product_format.ext}'
    }
    return data, status.HTTP_200_OK, {'ETag': product.checksum}


def get_log(source_id: int, checksum: str, output_format: str) -> Response:
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
    try:
        product_format = Format(output_format)
    except ValueError:  # Not a valid format.
        raise BadRequest('Invalid format')
    try:
        product = store.retrieve_log(source_id, checksum, product_format)
    except store.DoesNotExist as e:
        raise NotFound('No such compilation product') from e
    data = {
        'stream': product.stream,
        'content_type': product_format.content_type,
        'filename': f'{source_id}.{product_format.ext}'
    }
    return data, status.HTTP_200_OK, {'ETag': product.checksum}
