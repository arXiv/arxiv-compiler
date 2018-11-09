
"""Tests for :mod:`compiler.compiler`."""

import io
from tempfile import TemporaryDirectory, mkstemp
from unittest import TestCase, mock
from operator import itemgetter

import os.path
import subprocess

from importlib_resources import read_binary

from arxiv import status

from .. import compiler
from .. import domain, util
from ..services import filemanager

class TestCompile(TestCase):
    """Tests for :func:`compiler.compile`."""
    @mock.patch(f'{compiler.__name__}.store')
    @mock.patch(f'{compiler.__name__}.compile_source')
    @mock.patch(f'{compiler.__name__}.filemanager.get_source_content')
    def test_real_compiler(self, mock_get_source_content,
                           mock_compile_source, mock_store):
        """The compilation succeeds, and storage works without a hitch."""
        source_id = 'real-test'
        source_checksum = 'asdf12345checksum'
        tar_content = read_binary('compiler.tests', 'real-test.tar.gz')
        mock_get_source_content.return_value = domain.SourcePackage(
            stream=io.BytesIO(tar_content),
            source_id=source_id,
            etag=source_checksum
        )
        _, pdf_file = mkstemp(suffix='.pdf')
        _, log_file = mkstemp(suffix='.log')
        with open(pdf_file, 'wb') as f:
            f.write(b'foocontent')
        with open(log_file, 'wb') as f:
            f.write(b'foologs')

        mock_compile_source.return_value = (pdf_file, log_file)
        data = compiler.compile(source_id, source_checksum)
        self.assertEqual(data['source_id'], source_id)
        self.assertEqual(data['source_checksum'], source_checksum)
        self.assertEqual(data['format'], 'pdf')

        stored_product = mock_store.store.call_args[0][0]
        self.assertEqual(stored_product.status.status,
                         domain.CompilationStatus.Statuses.COMPLETED)
        self.assertEqual(stored_product.status.format,
                         domain.CompilationStatus.Formats.PDF)
        self.assertEqual(stored_product.status.source_checksum,
                         source_checksum)
