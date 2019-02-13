"""Tests for :mod:`compiler.start_compilationr`."""

import io
from tempfile import TemporaryDirectory, mkstemp, mkdtemp
from unittest import TestCase, mock
import shutil
from operator import itemgetter

import os.path
import subprocess

from importlib_resources import read_binary

from flask import Flask
from arxiv import status

from ..factory import create_app
from .. import compiler
from .. import domain, util
from ..services import filemanager

data_dir = os.path.join(os.path.dirname(__file__), 'data')


class TestDoCompile(TestCase):
    """Test main compilation routine."""

    @mock.patch(f'{compiler.__name__}.filemanager')
    @mock.patch(f'{compiler.__name__}._run')
    @mock.patch(f'{compiler.__name__}.store')
    def test_do_compile_success(self, mock_store, mock_run, mock_filemanager):
        """Everything goes according to plan."""
        container_source_root = mkdtemp()
        _, out_path = mkstemp()
        _, log_path = mkstemp()
        mock_run.return_value = (out_path, log_path)
        app = Flask('test')
        app.config.update({
            'CONTAINER_SOURCE_ROOT': container_source_root,
            'VERBOSE_COMPILE': True
        })
        with app.app_context():
            self.assertDictEqual(
                compiler.do_compile("1234", "asdf", "pdf", token="footoken"),
                {
                    'source_id': '1234',
                    'output_format': 'pdf',
                    'checksum': 'asdf',
                    'task_id': '1234::asdf::pdf',
                    'status': 'completed',
                    'reason': None,
                    'description': ''
                }
            )

    @mock.patch(f'{compiler.__name__}.filemanager')
    @mock.patch(f'{compiler.__name__}._run')
    @mock.patch(f'{compiler.__name__}.store')
    def test_unauthorized(self, mock_store, mock_run, mock_filemanager):
        """Request to filemanager is unauthorized."""
        container_source_root = mkdtemp()
        _, out_path = mkstemp()
        _, log_path = mkstemp()

        def raise_unauthorized(*args, **kwargs):
            raise filemanager.RequestUnauthorized('Nope!')

        mock_filemanager.RequestUnauthorized = filemanager.RequestUnauthorized
        mock_filemanager.RequestForbidden = filemanager.RequestForbidden
        mock_filemanager.get_source_content.side_effect = raise_unauthorized

        app = Flask('test')
        app.config.update({
            'CONTAINER_SOURCE_ROOT': container_source_root,
            'VERBOSE_COMPILE': True
        })
        with app.app_context():
            self.assertDictEqual(
                compiler.do_compile("1234", "asdf", "pdf", token="footoken"),
                {
                    'source_id': '1234',
                    'output_format': 'pdf',
                    'checksum': 'asdf',
                    'task_id': '1234::asdf::pdf',
                    'status': 'failed',
                    'reason': 'auth_error',
                    'description': 'There was a problem authorizing your'
                                   ' request.'
                }
            )

    @mock.patch(f'{compiler.__name__}.filemanager')
    @mock.patch(f'{compiler.__name__}._run')
    @mock.patch(f'{compiler.__name__}.store')
    def test_forbidden(self, mock_store, mock_run, mock_filemanager):
        """Request to filemanager is forbidden."""
        container_source_root = mkdtemp()
        _, out_path = mkstemp()
        _, log_path = mkstemp()

        def raise_forbidden(*args, **kwargs):
            raise filemanager.RequestForbidden('Nope!')

        mock_filemanager.RequestUnauthorized = filemanager.RequestUnauthorized
        mock_filemanager.RequestForbidden = filemanager.RequestForbidden
        mock_filemanager.get_source_content.side_effect = raise_forbidden

        app = Flask('test')
        app.config.update({
            'CONTAINER_SOURCE_ROOT': container_source_root,
            'VERBOSE_COMPILE': True
        })
        with app.app_context():
            self.assertDictEqual(
                compiler.do_compile("1234", "asdf", "pdf", token="footoken"),
                {
                    'source_id': '1234',
                    'output_format': 'pdf',
                    'checksum': 'asdf',
                    'task_id': '1234::asdf::pdf',
                    'status': 'failed',
                    'reason': 'auth_error',
                    'description': 'There was a problem authorizing your'
                                   ' request.'
                }
            )

    @mock.patch(f'{compiler.__name__}.filemanager')
    @mock.patch(f'{compiler.__name__}._run')
    @mock.patch(f'{compiler.__name__}.store')
    def test_connection_failed(self, mock_store, mock_run, mock_filemanager):
        """Request to filemanager fails."""
        container_source_root = mkdtemp()
        _, out_path = mkstemp()
        _, log_path = mkstemp()

        def raise_conn_failed(*args, **kwargs):
            raise filemanager.ConnectionFailed('Nope!')

        mock_filemanager.RequestUnauthorized = filemanager.RequestUnauthorized
        mock_filemanager.RequestForbidden = filemanager.RequestForbidden
        mock_filemanager.ConnectionFailed = filemanager.ConnectionFailed

        mock_filemanager.get_source_content.side_effect = raise_conn_failed

        app = Flask('test')
        app.config.update({
            'CONTAINER_SOURCE_ROOT': container_source_root,
            'VERBOSE_COMPILE': True
        })
        with app.app_context():
            self.assertDictEqual(
                compiler.do_compile("1234", "asdf", "pdf", token="footoken"),
                {
                    'source_id': '1234',
                    'output_format': 'pdf',
                    'checksum': 'asdf',
                    'task_id': '1234::asdf::pdf',
                    'status': 'failed',
                    'reason': 'network_error',
                    'description': 'There was a problem retrieving your source'
                                   ' files.'
                }
            )

    @mock.patch(f'{compiler.__name__}.filemanager')
    @mock.patch(f'{compiler.__name__}._run')
    @mock.patch(f'{compiler.__name__}.store')
    def test_not_found(self, mock_store, mock_run, mock_filemanager):
        """Request to filemanager fails because there is no source package."""
        container_source_root = mkdtemp()
        _, out_path = mkstemp()
        _, log_path = mkstemp()

        def raise_not_found(*args, **kwargs):
            raise filemanager.NotFound('Nope!')

        mock_filemanager.RequestUnauthorized = filemanager.RequestUnauthorized
        mock_filemanager.RequestForbidden = filemanager.RequestForbidden
        mock_filemanager.ConnectionFailed = filemanager.ConnectionFailed
        mock_filemanager.NotFound = filemanager.NotFound

        mock_filemanager.get_source_content.side_effect = raise_not_found

        app = Flask('test')
        app.config.update({
            'CONTAINER_SOURCE_ROOT': container_source_root,
            'VERBOSE_COMPILE': True
        })
        with app.app_context():
            self.assertDictEqual(
                compiler.do_compile("1234", "asdf", "pdf", token="footoken"),
                {
                    'source_id': '1234',
                    'output_format': 'pdf',
                    'checksum': 'asdf',
                    'task_id': '1234::asdf::pdf',
                    'status': 'failed',
                    'reason': 'missing_source',
                    'description': 'Could not retrieve a matching source'
                                   ' package'
                }
            )

    @mock.patch(f'{compiler.__name__}.filemanager')
    @mock.patch(f'{compiler.__name__}._run')
    @mock.patch(f'{compiler.__name__}.store')
    def test_source_corrupted(self, mock_store, mock_run, mock_filemanager):
        """There is a problem with the content of the source package."""
        container_source_root = mkdtemp()
        _, out_path = mkstemp()
        _, log_path = mkstemp()

        def raise_corrupted(*args, **kwargs):
            raise compiler.CorruptedSource('yuck')

        mock_run.side_effect = raise_corrupted

        app = Flask('test')
        app.config.update({
            'CONTAINER_SOURCE_ROOT': container_source_root,
            'VERBOSE_COMPILE': True
        })
        with app.app_context():
            self.assertDictEqual(
                compiler.do_compile("1234", "asdf", "pdf", token="footoken"),
                {
                    'source_id': '1234',
                    'output_format': 'pdf',
                    'checksum': 'asdf',
                    'task_id': '1234::asdf::pdf',
                    'status': 'failed',
                    'reason': 'corrupted_source',
                    'description': ''
                }
            )

    @mock.patch(f'{compiler.__name__}.filemanager')
    @mock.patch(f'{compiler.__name__}._run')
    @mock.patch(f'{compiler.__name__}.store')
    def test_no_output(self, mock_store, mock_run, mock_filemanager):
        """Compilation generates no output."""
        container_source_root = mkdtemp()
        _, log_path = mkstemp()

        mock_run.return_value = (None, log_path)

        app = Flask('test')
        app.config.update({
            'CONTAINER_SOURCE_ROOT': container_source_root,
            'VERBOSE_COMPILE': True
        })
        with app.app_context():
            self.assertDictEqual(
                compiler.do_compile("1234", "asdf", "pdf", token="footoken"),
                {
                    'source_id': '1234',
                    'output_format': 'pdf',
                    'checksum': 'asdf',
                    'task_id': '1234::asdf::pdf',
                    'status': 'failed',
                    'reason': 'compilation_errors',
                    'description': ''
                }
            )

    @mock.patch(f'{compiler.__name__}.filemanager')
    @mock.patch(f'{compiler.__name__}._run')
    @mock.patch(f'{compiler.__name__}.store')
    def test_cannot_save(self, mock_store, mock_run, mock_filemanager):
        """There is a problem storing the results."""
        container_source_root = mkdtemp()
        _, out_path = mkstemp()
        _, log_path = mkstemp()
        mock_run.return_value = (out_path, log_path)

        def raise_runtimeerror(*args, **kwargs):
            raise RuntimeError('yuck')

        mock_store.store.side_effect = raise_runtimeerror

        app = Flask('test')
        app.config.update({
            'CONTAINER_SOURCE_ROOT': container_source_root,
            'VERBOSE_COMPILE': True
        })
        with app.app_context():
            self.assertDictEqual(
                compiler.do_compile("1234", "asdf", "pdf", token="footoken"),
                {
                    'source_id': '1234',
                    'output_format': 'pdf',
                    'checksum': 'asdf',
                    'task_id': '1234::asdf::pdf',
                    'status': 'failed',
                    'reason': 'storage',
                    'description': 'Failed to store result'
                }
            )

    
#
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
