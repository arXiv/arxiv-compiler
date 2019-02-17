"""
Integration with the :mod:`filemanager` service API.

The file management service is responsible for accepting and processing user
uploads used for submissions. The core resource for the file management service
is the upload "workspace", which contains one or many files. We associate the
workspace with a submission prior to finalization. The workspace URI is used
for downpath processing, e.g. compilation.

A key requirement for this integration is the ability to path uploads to
the file management service as they are being received by this UI application.
"""
from functools import wraps
from typing import MutableMapping, Tuple
import json
import re
import os
from urllib.parse import urlparse, urlunparse, urlencode
import dateutil.parser
import tempfile

import requests
from urllib3.util.retry import Retry
from werkzeug.datastructures import FileStorage

from arxiv import status
from arxiv.base import logging
from arxiv.base.globals import get_application_config, get_application_global

from ...domain import SourcePackageInfo, SourcePackage

logger = logging.getLogger(__name__)


class RequestFailed(IOError):
    """The file management service returned an unexpected status code."""

    def __init__(self, msg: str, data: dict = {}) -> None:
        """Attach (optional) data to the exception."""
        self.data = data
        super(RequestFailed, self).__init__(msg)


class RequestUnauthorized(RequestFailed):
    """Client/user is not authenticated."""


class RequestForbidden(RequestFailed):
    """Client/user is not allowed to perform this request."""


class BadRequest(RequestFailed):
    """The request was malformed or otherwise improper."""


class Oversize(BadRequest):
    """The upload was too large."""


class NotFound(BadRequest):
    """The referenced upload does not exist."""


class BadResponse(RequestFailed):
    """The response from the file management service was malformed."""


class ConnectionFailed(IOError):
    """Could not connect to the file management service."""


class SecurityException(ConnectionFailed):
    """Raised when SSL connection fails."""


class FileManagementService(object):
    """Encapsulates a connection with the file management service."""

    def __init__(self, endpoint: str, verify_cert: bool = True,
                 headers: dict = {},
                 content_path: str = '/{source_id}/content') -> None:
        """
        Initialize an HTTP session.

        Parameters
        ----------
        endpoints : str
            One or more endpoints for metadata retrieval. If more than one
            are provided, calls to :meth:`.retrieve` will cycle through those
            endpoints for each call.
        verify_cert : bool
            Whether or not SSL certificate verification should enforced.
        headers : dict
            Headers to be included on all requests.
        content_path : str
            format()-able path string; should have ``source_id`` as a key.
        save_to : str
            Root directory for storing retrieved source packages. Each
            retrieved source will go into a separate directory in this
            location.

        """
        self._session = requests.Session()
        self._verify_cert = verify_cert
        self._retry = Retry(  # type: ignore
            total=10,
            read=10,
            connect=10,
            status=10,
            backoff_factor=0.5
        )
        self._adapter = requests.adapters.HTTPAdapter(max_retries=self._retry)
        self._session.mount(f'{urlparse(endpoint).scheme}://', self._adapter)
        if not endpoint.endswith('/'):
            endpoint += '/'
        self._endpoint = endpoint
        self._session.headers.update(headers)
        self._content_path = content_path

    def _path(self, path: str, query: dict = {}) -> str:
        o = urlparse(self._endpoint)
        path = path.lstrip('/')
        return urlunparse((  # type: ignore
            o.scheme, o.netloc, f"{o.path}{path}",
            None, urlencode(query), None
        ))

    def _make_request(self, method: str, path: str, expected_code: int = 200,
                      **kw) -> requests.Response:
        try:
            resp = getattr(self._session, method)(self._path(path), **kw)
            logger.debug('Got response %s', resp)
        except requests.exceptions.SSLError as e:
            raise SecurityException('SSL failed: %s' % e) from e
        except requests.exceptions.ConnectionError as e:
            raise ConnectionFailed('Could not connect: %s' % e) from e
        if resp.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            raise RequestFailed(f'Status: {resp.status_code}; {resp.content}')
        elif resp.status_code == status.HTTP_401_UNAUTHORIZED:
            raise RequestUnauthorized(f'Not authorized: {resp.content}')
        elif resp.status_code == status.HTTP_403_FORBIDDEN:
            raise RequestForbidden(f'Forbidden: {resp.content}')
        elif resp.status_code == status.HTTP_404_NOT_FOUND:
            raise NotFound(f'No such upload workspace: {path}')
        elif resp.status_code >= status.HTTP_400_BAD_REQUEST:
            raise BadRequest(f'Bad request: {resp.content}',
                             data=resp.content)
        elif resp.status_code is not expected_code:
            raise RequestFailed(f'Unexpected status code: {resp.status_code}')
        return resp

    def request(self, method: str, path: str, expected_code: int = 200, **kw) \
            -> Tuple[dict, MutableMapping]:
        """
        Perform an HTTP request, and handle any exceptions.

        Returns
        -------
        dict
            Response content.
        dict
            Response headers.
        """
        resp = self._make_request(method, path, expected_code, **kw)

        try:
            return resp.json(), resp.headers
        except json.decoder.JSONDecodeError as e:
            raise BadResponse(f'Could not decode: {resp.content}') from e

    def set_auth_token(self, token: str) -> None:
        """Set the authn/z token to use in subsequent requests."""
        self._session.headers.update({'Authorization': token})

    def get_service_status(self) -> dict:
        """Get the status of the file management service."""
        logger.debug('Get service status')
        content, headers = self.request('get', 'status')  # pylint: disable=unused-variable
        logger.debug('Got status response: %s', content)
        return content

    def get_source_content(self, source_id: str, save_to: str = '/tmp') \
            -> SourcePackage:
        """
        Retrieve the sanitized/processed upload package.

        Parameters
        ----------
        source_id : str
            Unique long-lived identifier for the upload.
        save_to : str
            Directory into which source should be saved.

        Returns
        -------
        :class:`SourcePackage`
            A ``read() -> bytes``-able wrapper around response content.

        """
        logger.debug('Get upload content for: %s', source_id)
        path = self._content_path.format(source_id=source_id)
        logger.debug('at path %s', path)
        response = self._make_request('get', path,
                                      status.HTTP_200_OK)
        logger.debug('Got response with status %s', response.status_code)
        source_file_path = self._save_content(path, source_id, response,
                                              save_to)

        logger.debug('wrote source content to %s', source_file_path)
        return SourcePackage(
            source_id=source_id,
            path=source_file_path,
            etag=response.headers['ETag']
        )

    def _save_content(self, path: str, source_id: str,
                      response: requests.Response, source_dir: str) -> str:
        match = re.search('filename=(.+)',
                          response.headers.get('content-disposition', ''))
        if match:
            filename = match.group(1).strip('"')
        else:
            filename = f'{source_id}.tar.gz'

        # There is a bug on the production public site: source downloads have
        # .gz extension, but are not in fact gzipped tarballs.
        if path.startswith('https://arxiv.org/src'):
            filename.rstrip('.gz')

        source_file_path = os.path.join(source_dir, filename)
        with open(source_file_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                if chunk:
                    f.write(chunk)
        return source_file_path

    def get_upload_info(self, source_id: str) -> SourcePackageInfo:
        """
        Get the current state of the source package/upload workspace.

        Parameters
        ------------
        source_id: str

        Returns
        ---------
        :class:`SourcePackageInfo`

        """
        logger.debug('Get upload info for: %s', source_id)
        response, headers = self.request('get', f'/{source_id}/content')
        logger.debug('Got response with etag %s', headers['ETag'])
        return SourcePackageInfo(source_id=source_id, etag=headers['ETag'])


def init_app(app: object = None) -> None:
    """Set default configuration parameters for an application instance."""
    config = get_application_config(app)
    config.setdefault('FILE_MANAGER_ENDPOINT', 'https://arxiv.org/')
    config.setdefault('FILE_MANAGER_VERIFY', True)
    config.setdefault('FILE_MANAGER_CONTENT_PATH', '/{source_id}/content')


def get_session(app: object = None) -> FileManagementService:
    """Get a new session with the file management endpoint."""
    config = get_application_config(app)
    endpoint = config.get('FILE_MANAGER_ENDPOINT', 'https://arxiv.org/')
    verify_cert = config.get('FILE_MANAGER_VERIFY', True)
    content_path = config.get('FILE_MANAGER_CONTENT_PATH',
                              '/{source_id}/content')
    logger.debug('Create FileManagementService with endpoint %s', endpoint)
    return FileManagementService(endpoint, verify_cert=verify_cert,
                                 content_path=content_path)


def current_session() -> FileManagementService:
    """Get/create :class:`.FileManagementService` for this context."""
    g = get_application_global()
    if not g:
        return get_session()
    elif 'filemanager' not in g:
        g.filemanager = get_session()   # type: ignore
    return g.filemanager    # type: ignore


@wraps(FileManagementService.set_auth_token)
def set_auth_token(token: str) -> None:
    """See :meth:`FileManagementService.set_auth_token`."""
    return current_session().set_auth_token(token)


@wraps(FileManagementService.get_source_content)
def get_source_content(source_id: str, save_to: str = '/tmp') -> SourcePackage:
    """See :meth:`FileManagementService.get_source_content`."""
    return current_session().get_source_content(source_id, save_to=save_to)


@wraps(FileManagementService.get_upload_info)
def get_upload_info(source_id: str) -> SourcePackageInfo:
    """See :meth:`FileManagementService.upload_package`."""
    return current_session().get_upload_info(source_id)


@wraps(FileManagementService.get_service_status)
def get_service_status() -> dict:
    """See :meth:`FileManagementService.get_service_status`."""
    return current_session().get_service_status()
