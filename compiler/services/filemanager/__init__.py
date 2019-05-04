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
from functools import wraps
from typing import MutableMapping, Tuple, Optional, Any
import json
import re
import os
from urllib.parse import urlparse, urlunparse, urlencode
import dateutil.parser
import tempfile

import requests
from urllib3.util.retry import Retry
from werkzeug.datastructures import FileStorage

from arxiv.integration.api import status, service
from arxiv.integration.api.exceptions import *
from arxiv.base import logging
from arxiv.base.globals import get_application_config, get_application_global

from ...domain import SourcePackageInfo, SourcePackage

logger = logging.getLogger(__name__)


class FileManager(service.HTTPIntegration):
    """Encapsulates a connection with the file management service."""

    class Meta:
        """Configuration for :class:`FileManagementService`."""

        service_name = "filemanager"

    def is_available(self) -> bool:
        """Check our connection to the filemanager service."""
        try:
            response = self.request('get', '/status')
            return response.status_code == 200
        except Exception as e:
            logger.error('Error when calling filemanager: %s', e)
            return False
        return True

    def owner(self, source_id: str, checksum: str, token: str) \
            -> Optional[str]:
        """Get the owner of a source package."""
        path = f'/{source_id}/content'

        response = self.request('head', path, token)
        if response.headers['ETag'] != checksum:
            raise RuntimeError('Not the resource we were looking for')
        return headers.get('ARXIV-OWNER')

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
        path = f'/{source_id}/content'
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

        source_file_path = os.path.join(source_dir, filename)
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
        response, _, headers = self.json('get', f'/{source_id}/content', token)
        logger.debug('Got response with etag %s', headers['ETag'])
        return SourcePackageInfo(source_id=source_id, etag=headers['ETag'])
