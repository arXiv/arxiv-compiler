from typing import Tuple

from werkzeug import MultiDict
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError

from flask import url_for

from arxiv import status
from arxiv.base import logging

from .services import store
from . import compiler
from .domain import CompilationStatus, CompilationProduct, Status, Format

logger = logging.getLogger(__name__)

ResponseData = Tuple[dict, int, dict]


def request_compilation(request_data: MultiDict) -> ResponseData:
    """Request compilation of an upload workspace."""
    try:
        source_id = request_data['source_id']
        checksum = request_data['checksum']
        output_format = Format(request_data['format'])
    except KeyError as e:
        raise BadRequest('Missing required parameter') from e
    preferred_compiler = request_data.get('compiler')
    force = request_data.get('force', False)

    try:
        info = store.get_status(source_id, checksum, output_format)
    except store.DoesNotExist as e:
        info = None
    except Exception as e:
        logger.error('Unhandled exception: %s', e)
        info = None

    if not force and info is not None:
        if info.status is Status.COMPLETED:
            location = url_for('api.get_product',
                               source_id=source_id, checksum=checksum,
                               output_format=output_format)
        else:
            location = url_for('api.get_status',
                               task_id=info.task_id)
        return {}, status.HTTP_303_SEE_OTHER, {'Location': location}
    try:
        task_id = compiler.create_compilation_task(
            source_id,
            checksum,
            output_format,
            preferred_compiler=preferred_compiler
        )
    except compiler.TaskCreationFailed as e:
        logger.error('Failed to start compilation: %s', e)
        raise InternalServerError('Failed to start compilation') from e
    location = url_for('api.get_status', task_id=task_id)
    return {}, status.HTTP_202_ACCEPTED, {'Location': location}


def get_info(source_id: int, checksum: str, output_format: str) \
        -> ResponseData:
    try:
        info = store.get_status(source_id, checksum,
                                Format(output_format))
    except store.DoesNotExist as e:
        raise NotFound('No such compilation') from e
    except Exception as e:
        logger.error('Unhandled exception: %s', e)
        raise InternalServerError('Unhandled exception: %s' % e)

    data = {'status': info.to_dict()}
    if info.status is Status.IN_PROGRESS:
        location = url_for('api.get_status', task_id=info.task_id)
        return data, status.HTTP_302_FOUND, {'Location': location}
    return data, status.HTTP_200_OK, {}


def get_status(task_id: str) -> ResponseData:
    try:
        info = compiler.get_compilation_task(task_id)
    except compiler.NoSuchTask as e:
        raise NotFound('No such compilation task') from e
    except Exception as e:
        logger.error('Unhandled exception: %s', e)
        raise InternalServerError('Unhandled exception: %s' % e)

    data = {'status': info.to_dict()}
    logger.debug(data)
    if info.status is Status.COMPLETED:
        location = url_for('api.get_info',
                           source_id=info.source_id,
                           checksum=info.source_etag,
                           output_format=info.output_format.value)
        return data, status.HTTP_303_SEE_OTHER, {'Location': location}
    return data, status.HTTP_200_OK, {}


def get_product(source_id: int, checksum: str, output_format: str) \
        -> ResponseData:
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


def get_log(source_id: int, checksum: str, output_format: str) -> ResponseData:
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
