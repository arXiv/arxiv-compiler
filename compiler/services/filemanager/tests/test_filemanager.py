"""Tests for :mod:`compiler.services.filemanager`."""

from unittest import TestCase, mock
import json
import requests
from arxiv import status

from ... import filemanager
from .... import domain, util


class TestAuthToken(TestCase):
    """Test :func:`.filemanager.set_auth_token`."""

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_set_auth_token(self, mock_Session):
        """Set the auth token for file manager requests."""
        headers = {}
        mock_Session.return_value = mock.MagicMock(headers=headers)
        filemanager.set_auth_token('footoken')
        self.assertEqual(headers['Authorization'], 'footoken',
                         "Authorization header is set")


class TestServiceStatus(TestCase):
    """Test :func:`.filemanager.get_service_status`."""

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_get_service_status(self, mock_Session):
        """Get the status of the file manager service sucessfully."""
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_200_OK,
                    json=mock.MagicMock(
                        return_value={'iam': 'ok'}
                    )
                )
            )
        )
        self.assertEqual(filemanager.get_service_status(), {'iam': 'ok'},
                         "Gets the response content from the status enpoint")


class TestGetUploadInfo(TestCase):
    """:func:`filemanager.get_upload_info` returns the current ETag."""

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_get_upload_info(self, mock_Session):
        """Get info for an upload workspace that exists."""
        etag = 'asdf12345checksum'
        source_id = '123456'
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_200_OK,
                    headers={'ETag': etag}
                )
            )
        )
        info = filemanager.get_upload_info(source_id)
        self.assertIsInstance(info, domain.SourcePackageInfo)
        self.assertEqual(info.etag, etag)
        self.assertEqual(info.source_id, source_id)

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_get_upload_info_nonexistant(self, mock_Session):
        """Get info for an upload workspace that does not exist."""
        source_id = '123456'
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_404_NOT_FOUND
                )
            )
        )
        with self.assertRaises(filemanager.NotFound):
            filemanager.get_upload_info(source_id)

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_get_upload_info_bad_request(self, mock_Session):
        """We made a bad request."""
        source_id = '123456'
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            )
        )
        with self.assertRaises(filemanager.BadRequest):
            filemanager.get_upload_info(source_id)

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_get_upload_info_unauthorized(self, mock_Session):
        """We made an unauthorized request."""
        source_id = '123456'
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_401_UNAUTHORIZED
                )
            )
        )
        with self.assertRaises(filemanager.RequestUnauthorized):
            filemanager.get_upload_info(source_id)

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_get_upload_info_forbidden(self, mock_Session):
        """We made a forbidden request."""
        source_id = '123456'
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_403_FORBIDDEN
                )
            )
        )
        with self.assertRaises(filemanager.RequestForbidden):
            filemanager.get_upload_info(source_id)

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_get_upload_info_error(self, mock_Session):
        """FM service replied 500 Internal Server Error."""
        source_id = '123456'
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            )
        )
        with self.assertRaises(filemanager.RequestFailed):
            filemanager.get_upload_info(source_id)

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_get_upload_info_bad_json(self, mock_Session):
        """FM service reurns bad JSON."""
        source_id = '123456'

        def raise_JSONDecodeError(*a, **k):
            raise json.decoder.JSONDecodeError('nope', 'nope', 0)

        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_200_OK,
                    json=mock.MagicMock(side_effect=raise_JSONDecodeError)
                )
            )
        )
        with self.assertRaises(filemanager.BadResponse):
            filemanager.get_upload_info(source_id)

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_get_upload_info_bad_ssl(self, mock_Session):
        """FM service has bad TLS."""
        source_id = '123456'

        def raise_ssl_error(*a, **k):
            raise requests.exceptions.SSLError('danger fill bobinson')

        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(side_effect=raise_ssl_error)
        )
        with self.assertRaises(filemanager.SecurityException):
            filemanager.get_upload_info(source_id)

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_get_upload_info_no_connection(self, mock_Session):
        """FM service cannot connect."""
        source_id = '123456'

        def raise_connection_error(*a, **k):
            raise requests.exceptions.ConnectionError('where r u')

        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(side_effect=raise_connection_error)
        )
        with self.assertRaises(filemanager.ConnectionFailed):
            filemanager.get_upload_info(source_id)


class TestGetUpload(TestCase):
    """:func:`filemanager.get_upload` returns the upload content."""

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_get_upload(self, mock_Session):
        """Get upload that exists."""
        etag = 'asdf12345checksum'
        source_id = '123456'
        content = b'foocontent'
        mock_iter_content = mock.MagicMock(return_value=[content])
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_200_OK,
                    iter_content=mock_iter_content,
                    headers={'ETag': etag}
                )
            )
        )
        info = filemanager.get_source_content(source_id)
        self.assertIsInstance(info, domain.SourcePackage)
        self.assertEqual(info.etag, etag)
        self.assertEqual(info.source_id, source_id)
        self.assertIsInstance(info.path, str)

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_get_upload_nonexistant(self, mock_Session):
        """Get info for an upload workspace that does not exist."""
        source_id = '123456'
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_404_NOT_FOUND
                )
            )
        )
        with self.assertRaises(filemanager.NotFound):
            filemanager.get_source_content(source_id)
