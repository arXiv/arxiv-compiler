"""Tests for :mod:`compiler.services.filemanager`."""

from unittest import TestCase, mock
from arxiv import status

from .. import filemanager
from ... import domain, util


class TestGetUploadInfo(TestCase):
    """:func:`filemanager.get_upload_info` returns the current ETag."""

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_get_upload_info(self, mock_Session):
        """Get info for an upload workspace that exists."""
        etag = 'asdf12345checksum'
        source_id = '123456'
        mock_Session.return_value = mock.MagicMock(
            head=mock.MagicMock(
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
            head=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_404_NOT_FOUND
                )
            )
        )
        with self.assertRaises(filemanager.NotFound):
            filemanager.get_upload_info(source_id)


class TestGetUpload(TestCase):
    """:func:`filemanager.get_upload` returns the upload content."""

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_get_upload(self, mock_Session):
        """Get upload that exists."""
        etag = 'asdf12345checksum'
        source_id = '123456'
        content = b'foocontent'
        mock_Session.return_value = mock.MagicMock(
            get=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_200_OK,
                    iter_content=mock.MagicMock(
                        return_value=content
                    ),
                    headers={'ETag': etag}
                )
            )
        )
        info = filemanager.get_upload_content(source_id)
        self.assertIsInstance(info, domain.SourcePackage)
        self.assertEqual(info.etag, etag)
        self.assertEqual(info.source_id, source_id)
        self.assertIsInstance(info.stream, util.ResponseStream)
        self.assertEqual(info.stream.read(), content)

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
            filemanager.get_upload_content(source_id)
