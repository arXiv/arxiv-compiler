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


def raise_not_found(*args, **kwargs):
    """Raise :class:`filemanager.NotFound`."""
    raise filemanager.NotFound('No sir')


class TestCompile(TestCase):
    """Tests for :func:`compiler.compile`."""

    @mock.patch(f'{compiler.__name__}.filemanager.get_source_content')
    def test_compile_nonexistant_source(self, mock_get_source_content):
        """The specified source does not exist."""
        source_id = 1234
        source_checksum = 'asdf12345checksum'
        mock_get_source_content.side_effect = raise_not_found

        with self.assertRaises(RuntimeError):
            compiler.compile(source_id, source_checksum)

    @mock.patch(f'{compiler.__name__}.filemanager.get_source_content')
    def test_compile_checksum_mismatch(self, mock_get_source_content):
        """The checksum on the source does not match the request."""
        source_id = 1234
        source_checksum = 'asdf12345checksum'
        mock_get_source_content.return_value = domain.SourcePackage(
            stream=io.BytesIO(b'foocontent'),
            source_id=source_id,
            etag='notthesamechecksum'
        )

        with self.assertRaises(RuntimeError):
            compiler.compile(source_id, source_checksum)

    @mock.patch(f'{compiler.__name__}.store')
    @mock.patch(f'{compiler.__name__}.compile_source')
    @mock.patch(f'{compiler.__name__}.filemanager.get_source_content')
    def test_compile_success(self, mock_get_source_content,
                             mock_compile_source, mock_store):
        """The compilation succeeds, and storage works without a hitch."""
        source_id = 1234
        source_checksum = 'asdf12345checksum'
        tar_content = read_binary('compiler.tests', 'test.tar.gz')
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


# class TestCompileUpload(TestCase):
#     """:func:`compiler.compile_upload` compiles the upload."""
#
#     @mock.patch(f'{compiler.__name__}.filemanager.get_source_content')
#     def test_compile_upload(self, mock_content):
#         """Get info for an upload workspace that exists."""
#         etag = 'asdf12345checksum'
#         upload_id = '123456'
#         content = importlib_resources.read_binary('compiler.tests', 'test.tar')
#         product_content = importlib_resources.read_binary('compiler.tests',
#                                                           'test.pdf')
#
#         mock_content.return_value = domain.SourcePackage(
#             source_id=upload_id,
#             stream=domain.ResponseStream(content),
#             etag=etag
#         )
#
#
#     @mock.patch(f'{compiler.__name__}.current_app')
#     def test_compile_source(self, mock_app):
#         content = importlib_resources.read_binary('compiler.tests', 'test.tar')
#         product_content = importlib_resources.read_binary('compiler.tests', 'test.pdf')
#
#         # compile the Dockerfile
#         with importlib_resources.path('compiler.tests', 'Dockerfile') as dockerfile:
#             DOCKER_IMAGE = 'arxiv-compiler-test'
#
#             DOCKERFILE_DIR = os.path.dirname(dockerfile)
#             cmd = f"docker build -t {DOCKER_IMAGE} {DOCKERFILE_DIR}"
#             result = subprocess.run(cmd, stdout=subprocess.PIPE,
#                                     stderr=subprocess.PIPE, shell=True)
#             if result.returncode:
#                 raise RuntimeError(f"Could not compile {DOCKER_IMAGE}: {cmd}")
#
#             # mock the current_app context
#             mock_app.return_value = mock.MagicMock(config=mock.MagicMock())
#             config_dict =  {'COMPILER_DOCKER_IMAGE': DOCKER_IMAGE}
#             mock_app.config.__getitem__.side_effect = config_dict.__getitem__
#
#             # Create temporary directories and attempt to use the test Dockerfile
#             with TemporaryDirectory(prefix='arxiv') as source_dir,\
#                 TemporaryDirectory(prefix='arxiv') as output_dir:
#
#                 # write the pass-through file
#                 with open(os.path.join(source_dir, "test.pdf"), 'wb') as outfile:
#                     outfile.write(product_content)
#
#                 compiler.compile_source(source_dir, output_dir)
#
#                 # verify the pass-through file
#                 with open(os.path.join(output_dir, "test.pdf"), 'rb') as outfile:
#                     self.assertEqual(product_content, outfile.read())
