"""Tests for :mod:`compiler.start_compilationr`."""

import io
from tempfile import TemporaryDirectory, mkstemp, mkdtemp
from unittest import TestCase, mock
import shutil
from operator import itemgetter

import os.path
import subprocess

from importlib_resources import read_binary

from arxiv import status

from ..factory import create_app
from .. import compiler
from .. import domain, util
from ..services import filemanager

data_dir = os.path.join(os.path.dirname(__file__), 'data')


# class TestCompile(TestCase):
#     """Tests for :func:`compiler.start_compilation`."""
#
#     @mock.patch(f'{compiler.__name__}.store')
#     @mock.patch(f'{compiler.__name__}.filemanager.get_source_content')
#     def test_real_compiler(self, mock_get_source_content, mock_store):
#         """The compilation succeeds, and storage works without a hitch."""
#         source_id = '1902.00123'
#         checksum = 'asdf12345checksum'
#         source_dir = mkdtemp()
#         fpath = os.path.join(source_dir, 'real-test.tar.gz')
#         shutil.copy(os.path.join(data_dir, 'real-test.tar.gz'), fpath)
#
#         mock_get_source_content.return_value = domain.SourcePackage(
#             path=fpath,
#             source_id=source_id,
#             etag=checksum
#         )
#
#         app = create_app()
#         with app.app_context():
#             data = compiler.start_compilation(source_id, checksum)
#         self.assertEqual(data['source_id'], source_id)
#         self.assertEqual(data['checksum'], checksum)
#         self.assertEqual(data['output_format'], 'pdf')
#
#         stored_product = mock_store.store.call_args[0][0]
#         self.assertEqual(stored_product.status.status,
#                          domain.Status.COMPLETED)
#         self.assertEqual(stored_product.status.format,
#                          domain.Format.PDF)
#         self.assertEqual(stored_product.status.checksum,
#                          checksum)
