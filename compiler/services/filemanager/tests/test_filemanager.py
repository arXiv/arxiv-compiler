"""Tests for :mod:`compiler.services.filemanager`."""

from unittest import TestCase, mock
import json
import os
import requests

from arxiv.integration.api import exceptions, status

from .. import FileManager
from .... import domain, util

CONFIG = {
    'FILEMANAGER_ENDPOINT': 'http://fooendpoint:1234',
    'FILEMANAGER_VERIFY': False
}
mock_app = mock.MagicMock(config=CONFIG)


class TestServiceStatus(TestCase):
    """Test :func:`.FileManager.get_status`."""

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_status(self, mock_Session):
        """Get the status of the file manager service sucessfully."""
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(return_value={'iam': 'ok'})
                )
            )
        )
        self.assertEqual(FileManager.get_status(), {'iam': 'ok'},
                         "Gets the response content from the status enpoint")


class TestGetUploadInfo(TestCase):
    """:func:`FileManager.get_upload_info` returns the current ETag."""

    def session(self, status_code=status.OK, method="get", json={},
                content="", headers={}):
        """Make a mock session."""
        return mock.MagicMock(**{
            method: mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status_code,
                    json=mock.MagicMock(
                        return_value=json
                    ),
                    content=content,
                    headers=headers
                )
            )
        })

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_upload_info(self, mock_Session):
        """Get info for an upload workspace that exists."""
        etag = 'asdf12345checksum'
        source_id = '123456'
        mock_Session.return_value = self.session(headers={'ETag': etag})
        info = FileManager.get_upload_info(source_id, 'footoken')
        self.assertIsInstance(info, domain.SourcePackageInfo)
        self.assertEqual(info.etag, etag)
        self.assertEqual(info.source_id, source_id)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_upload_info_nonexistant(self, mock_Session):
        """Get info for an upload workspace that does not exist."""
        source_id = '123456'
        mock_Session.return_value = self.session(status.NOT_FOUND)

        with self.assertRaises(exceptions.NotFound):
            FileManager.get_upload_info(source_id, 'footoken')

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_upload_info_bad_request(self, mock_Session):
        """We made a bad request."""
        source_id = '123456'
        mock_Session.return_value = self.session(status.BAD_REQUEST)
        with self.assertRaises(exceptions.BadRequest):
            FileManager.get_upload_info(source_id, 'footoken')

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_upload_info_unauthorized(self, mock_Session):
        """We made an unauthorized request."""
        source_id = '123456'
        mock_Session.return_value = self.session(status.UNAUTHORIZED)
        with self.assertRaises(exceptions.RequestUnauthorized):
            FileManager.get_upload_info(source_id, 'footoken')

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_upload_info_forbidden(self, mock_Session):
        """We made a forbidden request."""
        source_id = '123456'
        mock_Session.return_value = self.session(status.FORBIDDEN)

        with self.assertRaises(exceptions.RequestForbidden):
            FileManager.get_upload_info(source_id, 'footoken')

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_upload_info_error(self, mock_Session):
        """FM service replied 500 Internal Server Error."""
        source_id = '123456'
        mock_Session.return_value = self.session(
            status.INTERNAL_SERVER_ERROR
        )

        with self.assertRaises(exceptions.RequestFailed):
            FileManager.get_upload_info(source_id, 'footoken')

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_upload_info_bad_json(self, mock_Session):
        """FM service reurns bad JSON."""
        source_id = '123456'

        def raise_JSONDecodeError(*a, **k):
            raise json.decoder.JSONDecodeError('nope', 'nope', 0)

        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    json=mock.MagicMock(side_effect=raise_JSONDecodeError)
                )
            )
        )
        with self.assertRaises(exceptions.BadResponse):
            FileManager.get_upload_info(source_id, 'footoken')

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_upload_info_bad_ssl(self, mock_Session):
        """FM service has bad TLS."""
        source_id = '123456'

        def raise_ssl_error(*a, **k):
            raise requests.exceptions.SSLError('danger fill bobinson')

        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(side_effect=raise_ssl_error)
        )
        with self.assertRaises(exceptions.SecurityException):
            FileManager.get_upload_info(source_id, 'footoken')

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_upload_info_no_connection(self, mock_Session):
        """FM service cannot connect."""
        source_id = '123456'

        def raise_connection_error(*a, **k):
            raise requests.exceptions.ConnectionError('where r u')

        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(side_effect=raise_connection_error)
        )
        with self.assertRaises(exceptions.ConnectionFailed):
            FileManager.get_upload_info(source_id, 'footoken')


class TestGetUpload(TestCase):
    """:func:`FileManager.get_upload` returns the upload content."""

    def session(self, status_code=status.OK, method="get", json={},
                content="", headers={}):
        """Make a mock session."""
        return mock.MagicMock(**{
            method: mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status_code,
                    json=mock.MagicMock(
                        return_value=json
                    ),
                    content=content,
                    headers=headers
                )
            )
        })

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_upload(self, mock_Session):
        """Get upload that exists."""
        etag = 'asdf12345checksum'
        source_id = '123456'
        content = b'foocontent'
        mock_iter_content = mock.MagicMock(return_value=[content])
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    iter_content=mock_iter_content,
                    headers={'ETag': etag}
                )
            )
        )
        info = FileManager.get_source_content(source_id, 'footoken')
        self.assertIsInstance(info, domain.SourcePackage)
        self.assertEqual(info.etag, etag)
        self.assertEqual(info.source_id, source_id)
        self.assertIsInstance(info.path, str)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_upload_with_filename(self, mock_Session):
        """Get upload with an explicit filename in ``content-disposition``."""
        etag = 'asdf12345checksum'
        source_id = '123456'
        content = b'foocontent'
        mock_iter_content = mock.MagicMock(return_value=[content])
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    iter_content=mock_iter_content,
                    headers={'ETag': etag,
                             'content-disposition': 'filename=foo.tar.gz'}
                )
            )
        )
        info = FileManager.get_source_content(source_id, 'footoken')
        self.assertIsInstance(info, domain.SourcePackage)
        self.assertEqual(info.etag, etag)
        self.assertEqual(info.source_id, source_id)
        self.assertIsInstance(info.path, str)
        self.assertEqual(info.path, '/tmp/foo.tar.gz')
        self.assertTrue(os.path.exists(info.path))

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_upload_with_suspicious_filename(self, mock_Session):
        """Get upload with a suspicious filename in ``content-disposition``."""
        etag = 'asdf12345checksum'
        source_id = '123456'
        content = b'foocontent'
        mock_iter_content = mock.MagicMock(return_value=[content])
        filename = '../whereDoesThisGetWritten.txt'
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    iter_content=mock_iter_content,
                    headers={'ETag': etag,
                             'content-disposition': f'filename={filename}'}
                )
            )
        )
        with self.assertRaises(RuntimeError):
            FileManager.get_source_content(source_id, 'footoken')

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_upload_with_malicious_filename(self, mock_Session):
        """Get upload with a malicious filename in ``content-disposition``."""
        etag = 'asdf12345checksum'
        source_id = '123456'
        content = b'foocontent'
        mock_iter_content = mock.MagicMock(return_value=[content])
        filename = '//bin/bash'
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.OK,
                    iter_content=mock_iter_content,
                    headers={'ETag': etag,
                             'content-disposition': f'filename={filename}'}
                )
            )
        )
        with self.assertRaises(RuntimeError):
            FileManager.get_source_content(source_id, 'footoken')

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    @mock.patch('arxiv.integration.api.service.requests.Session')
    def test_get_upload_nonexistant(self, mock_Session):
        """Get info for an upload workspace that does not exist."""
        source_id = '123456'
        mock_Session.return_value = self.session(status.NOT_FOUND)
        with self.assertRaises(exceptions.NotFound):
            FileManager.get_source_content(source_id, 'footoken')
