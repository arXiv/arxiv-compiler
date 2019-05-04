"""Tests for :mod:`compiler.start_compilationr`."""

import io
from tempfile import TemporaryDirectory, mkstemp, mkdtemp
from unittest import TestCase, mock
import shutil
import tempfile
from operator import itemgetter

import os.path
import subprocess

from importlib_resources import read_binary

from flask import Flask
from arxiv.integration.api import exceptions, status

from ..factory import create_app
from .. import compiler
from .. import domain, util
from ..services import filemanager

data_dir = os.path.join(os.path.dirname(__file__), 'data')


class TestStartCompilation(TestCase):
    """Test :func:`start_compilation`."""

    @mock.patch(f'{compiler.__name__}.FileManager', mock.MagicMock())
    @mock.patch(f'{compiler.__name__}.do_compile', mock.MagicMock())
    @mock.patch(f'{compiler.__name__}.store', mock.MagicMock())
    def test_start_compilation_ok(self):
        """Compilation starts succesfully."""
        task_id = compiler.start_compilation('1234', 'asdf1234=', 'arXiv:1234',
                                             'http://arxiv.org/abs/1234',
                                             output_format=domain.Format.PDF,
                                             token='footoken')
        self.assertEqual(task_id, "1234/asdf1234=/pdf", "Returns task ID")

    @mock.patch(f'{compiler.__name__}.FileManager', mock.MagicMock())
    @mock.patch(f'{compiler.__name__}.do_compile')
    def test_start_compilation_errs(self, mock_do_compile):
        """An error occurs when starting compilation."""
        def raise_runtimeerror(*args, **kwargs):
            raise RuntimeError('Some error occurred')

        mock_do_compile.apply_async.side_effect = raise_runtimeerror
        with self.assertRaises(compiler.TaskCreationFailed):
            compiler.start_compilation('1234', 'asdf1234=',
                                       'arXiv:1234', 'http://arxiv.org/abs/1234',
                                       output_format=domain.Format.PDF,
                                       token='footoken')


class TestGetTask(TestCase):
    """Test :func:`get_task`."""

    @mock.patch(f'{compiler.__name__}.do_compile')
    def test_get_nonexistant_task(self, mock_do):
        """There is no such task."""
        # We set the status to SENT when we create the task.
        mock_do.AsyncResult.return_value = mock.MagicMock(status='PENDING')

        with self.assertRaises(compiler.NoSuchTask):
            compiler.get_task('1234', 'asdf1234=', domain.Format.PDF)

    @mock.patch(f'{compiler.__name__}.do_compile')
    def test_get_unstarted_task(self, mock_do):
        """Task exists, but has not started."""
        # We set the status to SENT when we create the task.
        mock_do.AsyncResult.return_value = mock.MagicMock(status='SENT')
        task = compiler.get_task('1234', 'asdf1234=', domain.Format.PDF)
        self.assertEqual(task.status, domain.Status.IN_PROGRESS)

    @mock.patch(f'{compiler.__name__}.do_compile')
    def test_get_started_task(self, mock_do):
        """Task exists and has started."""
        # We set the status to SENT when we create the task.
        mock_do.AsyncResult.return_value = mock.MagicMock(status='STARTED')
        task = compiler.get_task('1234', 'asdf1234=', domain.Format.PDF)
        self.assertEqual(task.status, domain.Status.IN_PROGRESS)

    @mock.patch(f'{compiler.__name__}.do_compile')
    def test_get_retry_task(self, mock_do):
        """Task exists and is being retried."""
        # We set the status to SENT when we create the task.
        mock_do.AsyncResult.return_value = mock.MagicMock(status='RETRY')
        task = compiler.get_task('1234', 'asdf1234=', domain.Format.PDF)
        self.assertEqual(task.status, domain.Status.IN_PROGRESS)

    @mock.patch(f'{compiler.__name__}.do_compile')
    def test_get_failed(self, mock_do):
        """Task exists and failed."""
        # We set the status to SENT when we create the task.
        mock_do.AsyncResult.return_value = mock.MagicMock(status='FAILURE')
        task = compiler.get_task('1234', 'asdf1234=', domain.Format.PDF)
        self.assertEqual(task.status, domain.Status.FAILED)

    @mock.patch(f'{compiler.__name__}.do_compile')
    def test_get_succeeded(self, mock_do):
        """Task exists and succeeded."""
        # We set the status to SENT when we create the task.
        mock_do.AsyncResult.return_value = mock.MagicMock(
            status='SUCCESS',
            result={}
        )
        task = compiler.get_task('1234', 'asdf1234=', domain.Format.PDF)
        self.assertEqual(task.status, domain.Status.COMPLETED)
        self.assertEqual(task.reason, domain.Reason.NONE)

    @mock.patch(f'{compiler.__name__}.do_compile')
    def test_get_failed_gracefully(self, mock_do):
        """Task exists and failed gracefully."""
        for reason in domain.Reason:
            mock_do.AsyncResult.return_value = mock.MagicMock(
                status='SUCCESS',
                result={'status': 'failed', 'reason': reason.value}
            )
            task = compiler.get_task('1234', 'asdf1234=', domain.Format.PDF)
            self.assertEqual(task.status, domain.Status.FAILED)
            self.assertEqual(task.reason, reason)


class TestDoCompile(TestCase):
    """Test main compilation routine."""

    @mock.patch(f'{compiler.__name__}.FileManager')
    @mock.patch(f'{compiler.__name__}._run')
    @mock.patch(f'{compiler.__name__}.store')
    def test_do_compile_success(self, mock_store, mock_run, mock_filemanager):
        """Everything goes according to plan."""
        container_source_root = mkdtemp()
        _, out_path = mkstemp()
        _, log_path = mkstemp()
        with open(out_path, 'a') as f:
            f.write('something is not nothing')
        mock_run.return_value = (out_path, log_path)
        app = Flask('test')
        app.config.update({
            'CONTAINER_SOURCE_ROOT': container_source_root,
            'VERBOSE_COMPILE': True
        })
        with app.app_context():
            self.assertDictEqual(
                compiler.do_compile("1234", "asdf", "arXiv:1234",
                                    "http://arxiv.org/abs/1234", "pdf",
                                    token="footoken"),
                {
                    'source_id': '1234',
                    'output_format': 'pdf',
                    'owner': None,
                    'checksum': 'asdf',
                    'task_id': '1234/asdf/pdf',
                    'status': 'completed',
                    'reason': None,
                    'description': '',
                    'size_bytes': 24
                }
            )

    @mock.patch(f'{compiler.__name__}.FileManager')
    @mock.patch(f'{compiler.__name__}._run')
    @mock.patch(f'{compiler.__name__}.store')
    def test_unauthorized(self, mock_store, mock_run, mock_filemanager):
        """Request to filemanager is unauthorized."""
        container_source_root = mkdtemp()
        _, out_path = mkstemp()
        _, log_path = mkstemp()

        def raise_unauthorized(*args, **kwargs):
            raise exceptions.RequestUnauthorized('Nope!', mock.MagicMock())

        mock_filemanager.get_source_content.side_effect = raise_unauthorized

        app = Flask('test')
        app.config.update({
            'CONTAINER_SOURCE_ROOT': container_source_root,
            'VERBOSE_COMPILE': True
        })
        with app.app_context():
            self.assertDictEqual(
                compiler.do_compile("1234", "asdf", "arXiv:1234",
                                    "http://arxiv.org/abs/1234", "pdf",
                                    token="footoken"),
                {
                    'source_id': '1234',
                    'output_format': 'pdf',
                    'owner': None,
                    'checksum': 'asdf',
                    'task_id': '1234/asdf/pdf',
                    'status': 'failed',
                    'reason': 'auth_error',
                    'description': 'There was a problem authorizing your'
                                   ' request.',
                    'size_bytes': 0
                }
            )

    @mock.patch(f'{compiler.__name__}.FileManager')
    @mock.patch(f'{compiler.__name__}._run')
    @mock.patch(f'{compiler.__name__}.store')
    def test_forbidden(self, mock_store, mock_run, mock_filemanager):
        """Request to filemanager is forbidden."""
        container_source_root = mkdtemp()
        _, out_path = mkstemp()
        _, log_path = mkstemp()

        def raise_forbidden(*args, **kwargs):
            raise exceptions.RequestForbidden('Nope!', mock.MagicMock())

        mock_filemanager.get_source_content.side_effect = raise_forbidden

        app = Flask('test')
        app.config.update({
            'CONTAINER_SOURCE_ROOT': container_source_root,
            'VERBOSE_COMPILE': True
        })
        with app.app_context():
            self.assertDictEqual(
                compiler.do_compile("1234", "asdf", "arXiv:1234",
                                    "http://arxiv.org/abs/1234", "pdf",
                                    token="footoken"),
                {
                    'source_id': '1234',
                    'output_format': 'pdf',
                    'owner': None,
                    'checksum': 'asdf',
                    'task_id': '1234/asdf/pdf',
                    'status': 'failed',
                    'reason': 'auth_error',
                    'description': 'There was a problem authorizing your'
                                   ' request.',
                    'size_bytes': 0
                }
            )

    @mock.patch(f'{compiler.__name__}.FileManager')
    @mock.patch(f'{compiler.__name__}._run')
    @mock.patch(f'{compiler.__name__}.store')
    def test_connection_failed(self, mock_store, mock_run, mock_filemanager):
        """Request to filemanager fails."""
        container_source_root = mkdtemp()
        _, out_path = mkstemp()
        _, log_path = mkstemp()

        def raise_conn_failed(*args, **kwargs):
            raise exceptions.ConnectionFailed('Nope!', mock.MagicMock())

        mock_filemanager.get_source_content.side_effect = raise_conn_failed

        app = Flask('test')
        app.config.update({
            'CONTAINER_SOURCE_ROOT': container_source_root,
            'VERBOSE_COMPILE': True
        })
        with app.app_context():
            self.assertDictEqual(
                compiler.do_compile("1234", "asdf", "arXiv:1234",
                                    "http://arxiv.org/abs/1234", "pdf",
                                    token="footoken"),
                {
                    'source_id': '1234',
                    'output_format': 'pdf',
                    'owner': None,
                    'checksum': 'asdf',
                    'task_id': '1234/asdf/pdf',
                    'status': 'failed',
                    'reason': 'network_error',
                    'description': 'There was a problem retrieving your source'
                                   ' files.',
                    'size_bytes': 0
                }
            )

    @mock.patch(f'{compiler.__name__}.FileManager')
    @mock.patch(f'{compiler.__name__}._run')
    @mock.patch(f'{compiler.__name__}.store')
    def test_not_found(self, mock_store, mock_run, mock_filemanager):
        """Request to filemanager fails because there is no source package."""
        container_source_root = mkdtemp()
        _, out_path = mkstemp()
        _, log_path = mkstemp()

        def raise_not_found(*args, **kwargs):
            raise exceptions.NotFound('Nope!', mock.MagicMock())

        mock_filemanager.get_source_content.side_effect = raise_not_found

        app = Flask('test')
        app.config.update({
            'CONTAINER_SOURCE_ROOT': container_source_root,
            'VERBOSE_COMPILE': True
        })
        with app.app_context():
            self.assertDictEqual(
                compiler.do_compile("1234", "asdf", "arXiv:1234",
                                    "http://arxiv.org/abs/1234", "pdf",
                                    token="footoken"),
                {
                    'source_id': '1234',
                    'output_format': 'pdf',
                    'owner': None,
                    'checksum': 'asdf',
                    'task_id': '1234/asdf/pdf',
                    'status': 'failed',
                    'reason': 'missing_source',
                    'description': 'Could not retrieve a matching source'
                                   ' package',
                    'size_bytes': 0
                }
            )

    @mock.patch(f'{compiler.__name__}.FileManager')
    @mock.patch(f'{compiler.__name__}._run')
    @mock.patch(f'{compiler.__name__}.store')
    def test_source_corrupted(self, mock_store, mock_run, mock_filemanager):
        """There is a problem with the content of the source package."""
        container_source_root = mkdtemp()
        _, out_path = mkstemp()
        _, log_path = mkstemp()

        def raise_corrupted(*args, **kwargs):
            raise compiler.CorruptedSource('yuck', mock.MagicMock())

        mock_run.side_effect = raise_corrupted

        app = Flask('test')
        app.config.update({
            'CONTAINER_SOURCE_ROOT': container_source_root,
            'VERBOSE_COMPILE': True
        })
        with app.app_context():
            self.assertDictEqual(
                compiler.do_compile("1234", "asdf", "arXiv:1234",
                                    "http://arxiv.org/abs/1234", "pdf",
                                    token="footoken"),
                {
                    'source_id': '1234',
                    'output_format': 'pdf',
                    'owner': None,
                    'checksum': 'asdf',
                    'task_id': '1234/asdf/pdf',
                    'status': 'failed',
                    'reason': 'corrupted_source',
                    'description': '',
                    'size_bytes': 0
                }
            )

    @mock.patch(f'{compiler.__name__}.FileManager')
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
                compiler.do_compile("1234", "asdf", "arXiv:1234",
                                    "http://arxiv.org/abs/1234", "pdf",
                                    token="footoken"),
                {
                    'source_id': '1234',
                    'output_format': 'pdf',
                    'owner': None,
                    'checksum': 'asdf',
                    'task_id': '1234/asdf/pdf',
                    'status': 'failed',
                    'reason': 'compilation_errors',
                    'description': '',
                    'size_bytes': 0
                }
            )

    @mock.patch(f'{compiler.__name__}.FileManager')
    @mock.patch(f'{compiler.__name__}._run')
    @mock.patch(f'{compiler.__name__}.store')
    def test_cannot_save(self, mock_store, mock_run, mock_filemanager):
        """There is a problem storing the results."""
        container_source_root = mkdtemp()
        _, out_path = mkstemp()
        _, log_path = mkstemp()
        mock_run.return_value = (out_path, log_path)

        def raise_runtimeerror(*args, **kwargs):
            raise RuntimeError('yuck', mock.MagicMock())

        mock_store.store.side_effect = raise_runtimeerror

        app = Flask('test')
        app.config.update({
            'CONTAINER_SOURCE_ROOT': container_source_root,
            'VERBOSE_COMPILE': True
        })
        with app.app_context():
            self.assertDictEqual(
                compiler.do_compile("1234", "asdf", "arXiv:1234",
                                    "http://arxiv.org/abs/1234", "pdf",
                                    token="footoken"),
                {
                    'source_id': '1234',
                    'output_format': 'pdf',
                    'owner': None,
                    'checksum': 'asdf',
                    'task_id': '1234/asdf/pdf',
                    'status': 'failed',
                    'reason': 'storage',
                    'description': 'Failed to store result',
                    'size_bytes': 0
                }
            )


class TestRun(TestCase):
    """Tests for :func:`.compiler._run`."""

    @mock.patch(f'{compiler.__name__}.run_docker')
    @mock.patch(f'{compiler.__name__}.current_app')
    def test_run(self, mock_current_app, mock_dock):
        """Compilation is successful."""
        source_dir = tempfile.mkdtemp()
        root, _ = os.path.split(source_dir)
        source_path = os.path.join(source_dir, 'foo.tar.gz')
        open(source_path, 'a').close()
        cache_dir = os.path.join(source_dir, 'tex_cache')
        log_dir = os.path.join(source_dir, 'tex_logs')
        os.makedirs(cache_dir)
        os.makedirs(log_dir)
        open(os.path.join(cache_dir, 'foo.pdf'), 'a').close()
        open(os.path.join(log_dir, 'autotex.log'), 'a').close()

        mock_current_app.config = {
            'COMPILER_DOCKER_IMAGE': 'foo/image:1234',
            'HOST_SOURCE_ROOT': '/dev/null/here',
            'CONTAINER_SOURCE_ROOT': root
        }
        mock_dock.return_value = (0, 'wooooo', '')
        pkg = domain.SourcePackage('1234', source_path, 'asdf1234=')
        out_path, log_path = compiler._run(pkg, "arXiv:1234",
                                           "http://arxiv.org/abs/1234")
        self.assertTrue(out_path.endswith('/tex_cache/foo.pdf'))
        self.assertTrue(log_path.endswith('/tex_logs/autotex.log'))
        shutil.rmtree(source_dir)  # Cleanup.

    @mock.patch(f'{compiler.__name__}.run_docker')
    @mock.patch(f'{compiler.__name__}.current_app')
    def test_run_fails(self, mock_current_app, mock_dock):
        """Compilation fails."""
        source_dir = tempfile.mkdtemp()
        root, _ = os.path.split(source_dir)
        source_path = os.path.join(source_dir, 'foo.tar.gz')
        open(source_path, 'a').close()
        cache_dir = os.path.join(source_dir, 'tex_cache')
        log_dir = os.path.join(source_dir, 'tex_logs')
        os.makedirs(cache_dir)
        os.makedirs(log_dir)
        open(os.path.join(log_dir, 'autotex.log'), 'a').close()

        mock_current_app.config = {
            'COMPILER_DOCKER_IMAGE': 'foo/image:1234',
            'HOST_SOURCE_ROOT': '/dev/null/here',
            'CONTAINER_SOURCE_ROOT': root
        }
        mock_dock.return_value = (0, 'wooooo', '')
        pkg = domain.SourcePackage('1234', source_path, 'asdf1234=')
        out_path, log_path = compiler._run(pkg, "arXiv:1234",
                                           "http://arxiv.org/abs/1234")
        self.assertIsNone(out_path)
        self.assertTrue(log_path.endswith('/tex_logs/autotex.log'))
        shutil.rmtree(source_dir)   # Cleanup.

#
# class TestCompile(TestCase):
#     """Tests for :func:`compiler.start_compilation`."""
#
#     @mock.patch(f'{compiler.__name__}.store')
#     @mock.patch(f'{compiler.__name__}.FileManager.get_source_content')
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
#         self.assertEqual(stored_product.task.status,
#                          domain.Status.COMPLETED)
#         self.assertEqual(stored_product.task.format,
#                          domain.Format.PDF)
#         self.assertEqual(stored_product.task.checksum,
#                          checksum)
