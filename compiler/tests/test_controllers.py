"""Tests for :mod:`compiler.controllers`."""

from unittest import TestCase, mock
import io

from werkzeug import MultiDict
from werkzeug.exceptions import NotFound, BadRequest

from arxiv import status

from ..domain import CompilationStatus, CompilationProduct, Format, Status
from .. import controllers
from ..services import store
from . import compiler


def mock_url_for(endpoint, **kwargs):
    """Simple mock for :func:`flask.url_for`."""
    params = '/'.join(map(str, kwargs.values()))
    return f'http://{endpoint}/{params}'


def raise_store_does_not_exist(*args, **kwargs):
    raise store.DoesNotExist('Nope!')


def raise_no_such_task(*args, **kwargs):
    raise compiler.NoSuchTask('Nope!')


class TestRequestCompilation(TestCase):
    """Tests for :func:`controllers.request_compilation`."""

    def test_request_missing_parameter(self):
        """Request for a new compilation with missing parameter."""
        with self.assertRaises(BadRequest):
            controllers.request_compilation(MultiDict({
                'source_id': 1234,
                'checksum': 'asdf12345zxcv'
            }))

        with self.assertRaises(BadRequest):
            controllers.request_compilation(MultiDict({
                'checksum': 'asdf12345zxcv',
                'format': 'pdf'
            }))

        with self.assertRaises(BadRequest):
            controllers.request_compilation(MultiDict({
                'source_id': 1234,
                'format': 'pdf'
            }))

    @mock.patch(f'{controllers.__name__}.url_for', mock_url_for)
    @mock.patch(f'{controllers.__name__}.compiler')
    @mock.patch(f'{controllers.__name__}.store')
    def test_request_compilation_de_novo(self, mock_store, mock_compiler):
        """Request for a new compilation."""
        mock_store.get_status.return_value = None
        task_id = '123::asdf12345zxcv::pdf'
        mock_compiler.create_compilation_task.return_value = task_id

        request_data = MultiDict({
            'source_id': 1234,
            'checksum': 'asdf12345zxcv',
            'format': 'pdf'
        })
        response_data = controllers.request_compilation(request_data)
        data, code, headers = response_data
        self.assertEqual(code, status.HTTP_202_ACCEPTED)
        self.assertIn('Location', headers)
        self.assertIn(str(request_data['source_id']), headers['Location'])
        self.assertIn(request_data['checksum'], headers['Location'])
        self.assertIn(request_data['format'], headers['Location'])

    @mock.patch(f'{controllers.__name__}.url_for', mock_url_for)
    @mock.patch(f'{controllers.__name__}.compiler')
    @mock.patch(f'{controllers.__name__}.store')
    def test_request_compilation_exists(self, mock_store, mock_compiler):
        """Request for a compilation that already exists."""
        task_id = '123::asdf12345zxcv::pdf'
        source_id = 1234
        checksum = 'asdf12345zxcv'
        format = 'pdf'
        mock_store.get_status.return_value = CompilationStatus(
            source_id=source_id,
            format=Format.PDF,
            status=Status.COMPLETED,
            task_id=task_id,
            source_etag=checksum
        )
        request_data = MultiDict({'source_id': source_id, 'checksum': checksum,
                                  'format': format})
        response_data = controllers.request_compilation(request_data)
        data, code, headers = response_data
        self.assertEqual(code, status.HTTP_303_SEE_OTHER)
        self.assertIn('Location', headers)
        self.assertIn(str(request_data['source_id']), headers['Location'])
        self.assertIn(request_data['checksum'], headers['Location'])
        self.assertIn(request_data['format'], headers['Location'])


class TestGetCompilationStatus(TestCase):
    """Tests for :func:`controllers.get_status`."""

    @mock.patch(f'{controllers.__name__}.url_for', mock_url_for)
    @mock.patch(f'{controllers.__name__}.compiler')
    def test_get_info_completed(self, mock_compiler):
        """Request for a completed compilation."""
        task_id = '123::asdf12345zxcv::pdf'
        source_id = 1234
        checksum = 'asdf12345zxcv'
        format = 'pdf'
        mock_compiler.get_compilation_task.return_value = CompilationStatus(
            source_id=source_id,
            format=Format.PDF,
            status=Status.COMPLETED,
            task_id=task_id,
            source_etag=checksum
        )
        response_data = controllers.get_status(source_id, checksum, format)
        data, code, headers = response_data
        self.assertEqual(code, status.HTTP_200_OK)

    @mock.patch(f'{controllers.__name__}.url_for', mock_url_for)
    @mock.patch(f'{controllers.__name__}.compiler')
    def test_get_info_in_progress(self, mock_compiler):
        """Request for a compilation in progress."""
        task_id = 'task1234'
        source_id = 1234
        checksum = 'asdf12345zxcv'
        format = 'pdf'
        mock_compiler.get_compilation_task.return_value = CompilationStatus(
            source_id=source_id,
            format=Format.PDF,
            status=Status.IN_PROGRESS,
            task_id=task_id,
            source_etag=checksum
        )
        response_data = controllers.get_status(source_id, checksum, format)
        data, code, headers = response_data
        self.assertEqual(code, status.HTTP_200_OK)

    @mock.patch(f'{controllers.__name__}.url_for', mock_url_for)
    @mock.patch(f'{controllers.__name__}.compiler')
    def test_get_info_nonexistant(self, mock_compiler):
        """Request for a nonexistant compilation."""
        source_id = 1234
        checksum = 'asdf12345zxcv'
        format = 'pdf'
        mock_compiler.NoSuchTask = compiler.NoSuchTask
        mock_compiler.get_compilation_task.side_effect = raise_no_such_task

        with self.assertRaises(NotFound):
            controllers.get_status(source_id, checksum, format)

    @mock.patch(f'{controllers.__name__}.url_for', mock_url_for)
    @mock.patch(f'{controllers.__name__}.compiler')
    def test_get_status_completed(self, mock_compiler):
        """Request for a completed compilation."""
        task_id = 'task1234'
        source_id = 1234
        checksum = 'asdf12345zxcv'
        format = 'pdf'
        mock_compiler.get_task.return_value = CompilationStatus(
            source_id=source_id,
            format=Format.PDF,
            status=Status.COMPLETED,
            task_id=task_id,
            source_etag=checksum
        )
        response_data = controllers.get_status(source_id, checksum, format)
        data, code, headers = response_data
        self.assertEqual(code, status.HTTP_200_OK)

    @mock.patch(f'{controllers.__name__}.url_for', mock_url_for)
    @mock.patch(f'{controllers.__name__}.compiler')
    def test_get_status_in_progress(self, mock_compiler):
        """Request for a completed compilation."""
        task_id = 'task1234'
        source_id = 1234
        checksum = 'asdf12345zxcv'
        mock_compiler.get_task.return_value = CompilationStatus(
            source_id=source_id,
            format=Format.PDF,
            status=Status.IN_PROGRESS,
            task_id=task_id,
            source_etag=checksum
        )
        response_data = controllers.get_status(source_id, checksum, format)
        data, code, headers = response_data
        self.assertEqual(code, status.HTTP_200_OK)


class TestGetCompilationProduct(TestCase):
    """Tests for :func:`controllers.get_product`."""

    @mock.patch(f'{controllers.__name__}.url_for', mock_url_for)
    @mock.patch(f'{controllers.__name__}.store')
    def test_get_product_completed(self, mock_store):
        """Request for a completed compilation product."""
        task_id = 'task1234'
        source_id = 1234
        checksum = 'asdf12345zxcv'
        format = 'pdf'
        product_checksum = 'thechecksumoftheproduct'
        mock_store.retrieve.return_value = CompilationProduct(
            stream=io.BytesIO(b'foocontent'),
            checksum=product_checksum,
            status=CompilationStatus(
                source_id=source_id,
                format=Format.PDF,
                status=Status.COMPLETED,
                task_id=task_id,
                source_etag=checksum
            )
        )
        response_data = controllers.get_product(
            source_id,
            checksum,
            format
        )
        data, code, headers = response_data
        self.assertEqual(code, status.HTTP_200_OK)
        self.assertEqual(headers['ETag'], product_checksum)

    @mock.patch(f'{controllers.__name__}.url_for', mock_url_for)
    @mock.patch(f'{controllers.__name__}.store')
    def test_get_product_nonexistant(self, mock_store):
        """Request for a nonexistant compilation product."""
        source_id = 1234
        checksum = 'asdf12345zxcv'
        format = 'pdf'
        mock_store.DoesNotExist = store.DoesNotExist
        mock_store.retrieve.side_effect = raise_store_does_not_exist

        with self.assertRaises(NotFound):
            controllers.get_product(source_id, checksum, format)


class TestGetCompilationLog(TestCase):
    """Tests for :func:`controllers.get_log`."""

    @mock.patch(f'{controllers.__name__}.url_for', mock_url_for)
    @mock.patch(f'{controllers.__name__}.store')
    def test_get_log_completed(self, mock_store):
        """Request log for a completed compilation."""
        task_id = 'task1234'
        source_id = 1234
        checksum = 'asdf12345zxcv'
        format = 'pdf'
        product_checksum = 'thechecksumoftheproduct'
        mock_store.retrieve_log.return_value = CompilationProduct(
            stream=io.BytesIO(b'foolog'),
            checksum=product_checksum,
            status=CompilationStatus(
                source_id=source_id,
                format=Format.PDF,
                status=Status.COMPLETED,
                task_id=task_id,
                source_etag=checksum
            )
        )
        response_data = controllers.get_log(
            source_id,
            checksum,
            format
        )
        data, code, headers = response_data
        self.assertEqual(code, status.HTTP_200_OK)
        self.assertEqual(headers['ETag'], product_checksum)

    @mock.patch(f'{controllers.__name__}.url_for', mock_url_for)
    @mock.patch(f'{controllers.__name__}.store')
    def test_get_log_nonexistant(self, mock_store):
        """Request for a nonexistant compilation log."""
        source_id = 1234
        checksum = 'asdf12345zxcv'
        format = 'pdf'
        mock_store.DoesNotExist = store.DoesNotExist
        mock_store.retrieve_log.side_effect = raise_store_does_not_exist

        with self.assertRaises(NotFound):
            controllers.get_log(source_id, checksum, format)
