"""Tests for :mod:`compiler.routes`."""

from unittest import TestCase, mock
import json
import io

from flask import Flask

from .. import routes
from arxiv import status


class TestRoutes(TestCase):
    """Tests for :mod:`compiler.routes`."""

    @mock.patch(f'{routes.__name__}.controllers')
    def setUp(self, mock_controllers):
        """Create an app and attach the routes blueprint."""
        self.app = Flask(__name__)
        self.app.register_blueprint(routes.blueprint)
        self.client = self.app.test_client()

    @mock.patch(f'{routes.__name__}.request')
    @mock.patch(f'{routes.__name__}.controllers')
    def test_compile(self, mock_controllers, mock_request):
        """POST request for compilation."""
        mock_request.environ = {'token': 'footoken'}
        response_data = {'da': 'ta'}
        mock_controllers.compile.return_value = (
            response_data, status.HTTP_200_OK, {}
        )
        response = self.client.post('/', json={
            'source_id': 1234,
            'checksum': 'asdf12345zxcv',
            'format': 'pdf'
        })
        self.assertEqual(mock_controllers.compile.call_count, 1)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(response.data), response_data)

    @mock.patch(f'{routes.__name__}.controllers')
    def test_get_info(self, mock_controllers):
        """GET request for compilation info."""
        response_data = {'da': 'ta'}
        mock_controllers.get_status.return_value = (
            response_data, status.HTTP_200_OK, {}
        )
        source_id = 1234
        checksum = 'asdf12345zxcv'
        format = 'pdf'
        response = self.client.get(f'/{source_id}/{checksum}/{format}')

        self.assertEqual(mock_controllers.get_status.call_count, 1)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            mock_controllers.get_info.called_with(source_id, checksum, format)
        )
        self.assertEqual(json.loads(response.data), response_data)

    @mock.patch(f'{routes.__name__}.controllers')
    def test_get_log(self, mock_controllers):
        """GET request for compilation log."""
        response_content = b'streamingdata'
        response_data = {
            'stream': io.BytesIO(response_content),
            'content_type': 'text/plain',
            'filename': 'log.txt'
        }
        mock_controllers.get_log.return_value = (
            response_data, status.HTTP_200_OK, {}
        )
        source_id = 1234
        checksum = 'asdf12345zxcv'
        format = 'pdf'
        response = self.client.get(f'/{source_id}/{checksum}/{format}/log')

        self.assertEqual(mock_controllers.get_log.call_count, 1)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            mock_controllers.get_log.called_with(source_id, checksum, format)
        )
        self.assertEqual(response.data, response_content)

    @mock.patch(f'{routes.__name__}.controllers')
    def test_get_product(self, mock_controllers):
        """GET request for compilation product."""
        response_content = b'streamingdata'
        etag = 'asdf1234etag'
        response_data = {
            'stream': io.BytesIO(response_content),
            'content_type': 'application/pdf',
            'filename': '1234.pdf'
        }
        mock_controllers.get_product.return_value = (
            response_data, status.HTTP_200_OK, {'ETag': etag}
        )
        source_id = 1234
        checksum = 'asdf12345zxcv'
        format = 'pdf'
        response = self.client.get(f'/{source_id}/{checksum}/{format}/product')

        self.assertEqual(mock_controllers.get_product.call_count, 1)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            mock_controllers.get_product.called_with(
                source_id, checksum, format
            )
        )
        self.assertEqual(response.data, response_content)
        self.assertEqual(response.headers['ETag'], f'"{etag}"')
