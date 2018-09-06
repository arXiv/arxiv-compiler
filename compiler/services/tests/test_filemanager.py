"""Tests for :mod:`compiler.services.filemanager`."""

from unittest import TestCase, mock
from arxiv import status

from .. import filemanager
from ... import domain


class TestGetUploadInfo(TestCase):
    """:func:`filemanager.get_upload_info` returns the current ETag."""

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_get_upload_info(self, mock_Session):
        """Get info for an upload workspace that exists."""
        etag = 'asdf12345checksum'
        upload_id = '123456'
        mock_Session.return_value = mock.MagicMock(
            head=mock.MagicMock(
                return_value=mock.MagicMock(
                    status_code=status.HTTP_200_OK,
                    headers={'ETag': etag}
                )
            )
        )
        info = filemanager.get_upload_info(upload_id)
        self.assertIsInstance(info, domain.SourcePackageInfo)
        self.assertEqual(info.etag, etag)
        self.assertEqual(info.upload_id, upload_id)
