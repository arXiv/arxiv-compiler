"""Test the compiler application as a whole."""

from unittest import TestCase, mock
from arxiv import status
from .. import factory, compiler
from ..services import store, filemanager


class TestCompilerApp(TestCase):
    """The the app API."""

    def setUp(self):
        """Create a test app and client."""
        self.app = factory.create_app()
        self.client = self.app.test_client()

    def test_get_status(self):
        """GET the ``getServiceStatus`` endpoint."""
        response = self.client.get('/status')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_nonexistant(self):
        """GET a nonexistant endpoint."""
        response = self.client.get('/nowhere')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.json,
            {'reason': 'The requested URL was not found on the server.  If you'
                       ' entered the URL manually please check your spelling'
                       ' and try again.'}
        )

    def test_post_bad_request(self):
        """POST the ``requestCompilation`` endpoint without data."""
        response = self.client.post('/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json,
            {'reason': 'The browser (or proxy) sent a request that this server'
                       ' could not understand.'}
        )

    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_post_request_compilation(self, mock_store, mock_compiler):
        """POST the ``requestCompilation`` endpoint with valid data."""
        mock_store.DoesNotExist = store.DoesNotExist
        mock_compiler.NoSuchTask = compiler.NoSuchTask

        def raise_does_not_exist(*args, **kwargs):
            raise store.DoesNotExist('Nope')

        def raise_no_such_task(*args, **kwargs):
            raise compiler.NoSuchTask('Nada')

        mock_store.get_status.side_effect = raise_does_not_exist
        mock_compiler.get_task.side_effect = raise_no_such_task

        response = self.client.post('/', json={
            'source_id': '54',
            'checksum': 'a1b2c3d4=',
            'output_format': 'pdf'
        })

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.headers['Location'],
                         'http://localhost/54/a1b2c3d4%3D/pdf')
