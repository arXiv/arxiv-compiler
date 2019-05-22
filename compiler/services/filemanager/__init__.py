"""
Integration with the :mod:`filemanager` service API.

The file management service is responsible for accepting and processing user
uploads used for submissions. The core resource for the file management service
is the upload "workspace", which contains one or many files. We associate the
workspace with a submission prior to finalization. The workspace URI is used
for downpath processing, e.g. compilation.

A key requirement for this integration is the ability to pass uploads to
the file management service as they are being received by this UI application.
"""

from typing import Optional, Any
import json
import re
import os

import requests
from arxiv.integration.api import status, service
from arxiv.base import logging
from arxiv.base.globals import get_application_config

from ...domain import SourcePackageInfo, SourcePackage

logger = logging.getLogger(__name__)


class Default(dict):
    """A more palatable dict for string formatting."""

    def __missing__(self, key: str) -> str:
        """Return a key when missing rather than raising a KeyError."""
        return key


class FileManager(service.HTTPIntegration):
    """Encapsulates a connection with the file management service."""

    class Meta:
        """Configuration for :class:`FileManagementService`."""

        service_name = "filemanager"

    def is_available(self, **kwargs: Any) -> bool:
        """Check our connection to the filemanager service."""
        config = get_application_config()
        status_endpoint = config.get('FILEMANAGER_STATUS_ENDPOINT', 'status')
        try:
            response = self.request('get', status_endpoint)
            return bool(response.status_code == 200)
        except Exception as e:
            logger.error('Error when calling filemanager: %s', e)
            return False
        return True

    def owner(self, source_id: str, checksum: str, token: str) \
            -> Optional[str]:
        """Get the owner of a source package."""
        config = get_application_config()
        content_endpoint = config.get('FILEMANAGER_CONTENT_PATH',
                                      '/{source_id}/content')
        path = content_endpoint.format_map(Default(source_id=source_id))
        response = self.request('head', path, token)
        if response.headers['ETag'] != checksum:
            raise RuntimeError('Not the resource we were looking for')
        owner: Optional[str] = response.headers.get('ARXIV-OWNER')
        return owner

    def get_source_content(self, source_id: str, token: str,
                           save_to: str = '/tmp') -> SourcePackage:
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
        config = get_application_config()
        content_endpoint = config.get('FILEMANAGER_CONTENT_PATH',
                                      '/{source_id}/content')
        path = content_endpoint.format_map(Default(source_id=source_id))
        response = self.request('get', path, token)
        logger.debug('Got response with status %s', response.status_code)
        source_file_path = self._save_content(path, source_id, response,
                                              save_to)
        logger.debug('wrote source content to %s', source_file_path)
        return SourcePackage(source_id=source_id, path=source_file_path,
                             etag=response.headers['ETag'])

    def _save_content(self, path: str, source_id: str,
                      response: requests.Response, source_dir: str) -> str:
        # Get the filename from the response headers.
        match = re.search('filename=(.+)',
                          response.headers.get('content-disposition', ''))
        if match:
            filename = match.group(1).strip('"')
        else:   # Or make one ourselves.
            filename = f'{source_id}.tar.gz'

        # There is a bug on the production public site: source downloads have
        # .gz extension, but are not in fact gzipped tarballs.
        if path.startswith('https://arxiv.org/src'):
            filename.rstrip('.gz')

        source_file_path = os.path.abspath(os.path.join(source_dir, filename))
        if not source_file_path.startswith(source_dir):
            logger.error('Source file path would escape working filesystem'
                         ' context; may be malicious: %s', source_file_path)
            raise RuntimeError(f'Bad source file path: {source_file_path}')

        with open(source_file_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                if chunk:
                    f.write(chunk)
        return source_file_path

    def get_upload_info(self, source_id: str, token: str) -> SourcePackageInfo:
        """
        Get the current state of the source package/upload workspace.

        Parameters
        ----------
        source_id: str

        Returns
        -------
        :class:`SourcePackageInfo`

        """
        logger.debug('Get upload info for: %s', source_id)
        config = get_application_config()
        content_endpoint = config.get('FILEMANAGER_CONTENT_PATH',
                                      '/{source_id}/content')
        path = content_endpoint.format_map(Default(source_id=source_id))
        response, _, headers = self.json('get', path, token)
        logger.debug('Got response with etag %s', headers['ETag'])
        return SourcePackageInfo(source_id=source_id, etag=headers['ETag'])
