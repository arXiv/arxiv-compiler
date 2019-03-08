"""Test the compiler application as a whole."""

from unittest import TestCase, mock
import io

from arxiv.integration.api import status
from arxiv.users.helpers import generate_token
from arxiv.users.auth import scopes

from .. import factory, compiler, domain
from ..services import store, filemanager


OS_ENVIRON = {'JWT_SECRET': 'foosecret'}


class TestCompilerApp(TestCase):
    """The the app API."""

    def setUp(self):
        """Create a test app and client."""
        self.app = factory.create_app()
        self.client = self.app.test_client()
        self.app.config['JWT_SECRET'] = 'foosecret'
        self.user_id = '123'
        with self.app.app_context():
            self.token = generate_token(self.user_id, 'foo@user.com',
                                        'foouser',
                                        scope=[scopes.CREATE_COMPILE,
                                               scopes.READ_COMPILE])

    @staticmethod
    def raise_does_not_exist(*args, **kwargs):
        """Raise :class:`store.DoesNotExist`."""
        raise store.DoesNotExist('Nope')

    @staticmethod
    def raise_no_such_task(*args, **kwargs):
        """Raise :class:`compiler.NoSuchTask`."""
        raise compiler.NoSuchTask('Nada')

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

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    def test_post_bad_request(self):
        """POST the ``requestCompilation`` endpoint without data."""
        response = self.client.post('/', headers={'Authorization': self.token})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json,
            {'reason': 'The browser (or proxy) sent a request that this server'
                       ' could not understand.'}
        )

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_post_request_compilation(self, mock_store, mock_compiler):
        """POST the ``requestCompilation`` endpoint with valid data."""
        mock_store.DoesNotExist = store.DoesNotExist
        mock_compiler.NoSuchTask = compiler.NoSuchTask

        mock_store.get_status.side_effect = self.raise_does_not_exist
        mock_compiler.get_task.side_effect = self.raise_no_such_task

        response = self.client.post('/', json={
                'source_id': '54',
                'checksum': 'a1b2c3d4=',
                'output_format': 'pdf'
            },
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.headers['Location'],
                         'http://localhost/54/a1b2c3d4%3D/pdf')

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_post_compilation_product_exists(self, mock_store, mock_compiler):
        """POST ``requestCompilation`` for existant product."""
        mock_store.DoesNotExist = store.DoesNotExist
        mock_compiler.NoSuchTask = compiler.NoSuchTask

        source_id = '54'
        checksum = 'a1b2c3d4='
        fmt = 'pdf'
        owner = self.user_id

        comp_status = domain.Task.from_dict({
            'status': 'completed',
            'reason': None,
            'source_id': source_id,
            'output_format': fmt,
            'checksum': checksum,
            'size_bytes': 123456,
            'owner': owner,
            'task_id': f'{source_id}/{checksum}/{fmt}'
        })
        mock_store.get_status.return_value = comp_status
        mock_compiler.get_task.side_effect = self.raise_no_such_task

        response = self.client.post('/', json={
                'source_id': source_id,
                'checksum': checksum,
                'output_format': fmt
            },
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.HTTP_303_SEE_OTHER)
        self.assertEqual(response.headers['Location'],
                         f'http://localhost/{source_id}/a1b2c3d4%3D/{fmt}')

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_product_exists_unauthorized(self, mock_store, mock_compiler):
        """POST ``requestCompilation`` for existant product, wrong owner."""
        mock_store.DoesNotExist = store.DoesNotExist
        mock_compiler.NoSuchTask = compiler.NoSuchTask

        source_id = '54'
        checksum = 'a1b2c3d4='
        fmt = 'pdf'
        owner = '84843'

        comp_status = domain.Task.from_dict({
            'status': 'completed',
            'reason': None,
            'source_id': source_id,
            'output_format': fmt,
            'checksum': checksum,
            'size_bytes': 123456,
            'owner': owner,
            'task_id': f'{source_id}/{checksum}/{fmt}'
        })
        mock_store.get_status.return_value = comp_status
        mock_compiler.get_task.side_effect = self.raise_no_such_task

        response = self.client.post('/', json={
                'source_id': source_id,
                'checksum': checksum,
                'output_format': fmt
            },
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_post_compilation_task_exists(self, mock_store, mock_compiler):
        """POST ``requestCompilation`` for existant compilation task."""
        mock_store.DoesNotExist = store.DoesNotExist
        mock_compiler.NoSuchTask = compiler.NoSuchTask

        source_id = '54'
        checksum = 'a1b2c3d4='
        fmt = 'pdf'
        owner = self.user_id

        comp_status = domain.Task.from_dict({
            'status': 'completed',
            'reason': None,
            'source_id': source_id,
            'output_format': fmt,
            'checksum': checksum,
            'size_bytes': 123456,
            'owner': owner,
            'task_id': f'{source_id}/{checksum}/{fmt}'
        })
        mock_store.get_status.side_effect = self.raise_does_not_exist
        mock_compiler.get_task.return_value = comp_status

        response = self.client.post('/', json={
                'source_id': source_id,
                'checksum': checksum,
                'output_format': fmt
            },
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.HTTP_303_SEE_OTHER)
        self.assertEqual(response.headers['Location'],
                         f'http://localhost/{source_id}/a1b2c3d4%3D/{fmt}')

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_task_exists_unauthorized(self, mock_store, mock_compiler):
        """POST ``requestCompilation`` for existant task with other owner."""
        mock_store.DoesNotExist = store.DoesNotExist
        mock_compiler.NoSuchTask = compiler.NoSuchTask

        source_id = '54'
        checksum = 'a1b2c3d4='
        fmt = 'pdf'
        owner = '84839'

        comp_status = domain.Task.from_dict({
            'status': 'completed',
            'reason': None,
            'source_id': source_id,
            'output_format': fmt,
            'checksum': checksum,
            'size_bytes': 123456,
            'owner': owner,
            'task_id': f'{source_id}/{checksum}/{fmt}'
        })
        mock_store.get_status.side_effect = self.raise_does_not_exist
        mock_compiler.get_task.return_value = comp_status

        response = self.client.post('/', json={
                'source_id': source_id,
                'checksum': checksum,
                'output_format': fmt
            },
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_post_task_start_failed(self, mock_store, mock_compiler):
        """Could not start compilation."""
        mock_store.DoesNotExist = store.DoesNotExist
        mock_compiler.NoSuchTask = compiler.NoSuchTask
        mock_compiler.TaskCreationFailed = compiler.TaskCreationFailed

        mock_store.get_status.side_effect = self.raise_does_not_exist
        mock_compiler.get_task.side_effect = self.raise_no_such_task

        def raise_creation_failed(*args, **kwargs):
            raise compiler.TaskCreationFailed('Nope')

        mock_compiler.start_compilation.side_effect = raise_creation_failed

        response = self.client.post('/', json={
                'source_id': '54',
                'checksum': 'a1b2c3d4=',
                'output_format': 'pdf'
            },
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code,
                         status.HTTP_500_INTERNAL_SERVER_ERROR)

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_get_status_completed(self, mock_store, mock_compiler):
        """GET the ``getCompilationStatus`` endpoint with valid data."""
        mock_store.DoesNotExist = store.DoesNotExist
        mock_compiler.NoSuchTask = compiler.NoSuchTask

        source_id = '54'
        checksum = 'a1b2c3d4='
        fmt = 'pdf'
        owner = self.user_id

        comp_status = domain.Task.from_dict({
            'status': 'completed',
            'reason': None,
            'source_id': source_id,
            'output_format': fmt,
            'checksum': checksum,
            'size_bytes': 123456,
            'owner': owner,
            'task_id': f'{source_id}/{checksum}/{fmt}'
        })
        mock_store.get_status.return_value = comp_status

        response = self.client.get(
            f'/{source_id}/{checksum}/{fmt}',
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(response.json, comp_status.to_dict())

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_get_status_not_owner(self, mock_store, mock_compiler):
        """Someone other than the owner requests ``getCompilationStatus``."""
        mock_store.DoesNotExist = store.DoesNotExist
        mock_compiler.NoSuchTask = compiler.NoSuchTask

        source_id = '54'
        checksum = 'a1b2c3d4='
        fmt = 'pdf'
        owner = '5943'

        comp_status = domain.Task.from_dict({
            'status': 'completed',
            'reason': None,
            'source_id': source_id,
            'output_format': fmt,
            'checksum': checksum,
            'size_bytes': 123456,
            'owner': owner,
            'task_id': f'{source_id}/{checksum}/{fmt}'
        })
        mock_store.get_status.return_value = comp_status

        response = self.client.get(
            f'/{source_id}/{checksum}/{fmt}',
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN,
                         'Forbidden user gets a 403 Forbidden response.')

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_get_status_nonexistant(self, mock_store, mock_compiler):
        """GET ``getCompilationStatus`` for nonexistant task."""
        mock_store.DoesNotExist = store.DoesNotExist
        mock_compiler.NoSuchTask = compiler.NoSuchTask

        source_id = '54'
        checksum = 'a1b2c3d4='
        fmt = 'pdf'

        mock_store.get_status.side_effect = self.raise_does_not_exist
        mock_compiler.get_task.side_effect = self.raise_no_such_task

        response = self.client.get(
            f'/{source_id}/{checksum}/{fmt}',
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_get_status_invalid_format(self, mock_store, mock_compiler):
        """GET ``getCompilationStatus`` for unsupported format."""
        source_id = '54'
        checksum = 'a1b2c3d4='
        fmt = 'wav'
        response = self.client.get(
            f'/{source_id}/{checksum}/{fmt}',
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_get_log(self, mock_store, mock_compiler):
        """GET the ``getCompilationLog`` endpoint with valid data."""
        mock_store.DoesNotExist = store.DoesNotExist
        mock_compiler.NoSuchTask = compiler.NoSuchTask

        source_id = '54'
        checksum = 'a1b2c3d4='
        fmt = 'pdf'
        owner = self.user_id

        comp_status = domain.Task.from_dict({
            'status': 'completed',
            'reason': None,
            'source_id': source_id,
            'output_format': fmt,
            'checksum': checksum,
            'size_bytes': 123456,
            'owner': owner,
            'task_id': f'{source_id}/{checksum}/{fmt}'
        })
        comp_log = domain.Product(stream=io.BytesIO(b'foologcontent'))
        mock_store.get_status.return_value = comp_status
        mock_store.retrieve_log.return_value = comp_log

        response = self.client.get(
            f'/{source_id}/{checksum}/{fmt}/log',
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, b'foologcontent',
                         "Returns the raw log content")
        self.assertEqual(response.headers['Content-Type'],
                         'text/plain; charset=utf-8')

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_get_log_not_owner(self, mock_store, mock_compiler):
        """GET the ``getCompilationLog`` by someone who is not the owner."""
        mock_store.DoesNotExist = store.DoesNotExist
        mock_compiler.NoSuchTask = compiler.NoSuchTask

        source_id = '54'
        checksum = 'a1b2c3d4='
        fmt = 'pdf'
        owner = '98766'

        comp_status = domain.Task.from_dict({
            'status': 'completed',
            'reason': None,
            'source_id': source_id,
            'output_format': fmt,
            'checksum': checksum,
            'size_bytes': 123456,
            'owner': owner,
            'task_id': f'{source_id}/{checksum}/{fmt}'
        })
        comp_log = domain.Product(stream=io.BytesIO(b'foologcontent'))
        mock_store.get_status.return_value = comp_status
        mock_store.retrieve_log.return_value = comp_log

        response = self.client.get(
            f'/{source_id}/{checksum}/{fmt}/log',
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_get_log_nononexistant(self, mock_store, mock_compiler):
        """GET the ``getCompilationLog`` for nonexistant compilation."""
        mock_store.DoesNotExist = store.DoesNotExist
        mock_compiler.NoSuchTask = compiler.NoSuchTask

        source_id = '54'
        checksum = 'a1b2c3d4='
        fmt = 'pdf'

        mock_store.get_status.side_effect = self.raise_does_not_exist

        response = self.client.get(
            f'/{source_id}/{checksum}/{fmt}/log',
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_get_log_invalid_format(self, mock_store, mock_compiler):
        """GET the ``getCompilationLog`` for unsupported format."""
        source_id = '54'
        checksum = 'a1b2c3d4='
        fmt = 'wav'

        response = self.client.get(
            f'/{source_id}/{checksum}/{fmt}/log',
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_get_product(self, mock_store, mock_compiler):
        """GET the ``getCompilationProduct`` endpoint with valid data."""
        mock_store.DoesNotExist = store.DoesNotExist
        mock_compiler.NoSuchTask = compiler.NoSuchTask

        source_id = '54'
        checksum = 'a1b2c3d4='
        fmt = 'pdf'
        owner = self.user_id

        comp_status = domain.Task.from_dict({
            'status': 'completed',
            'reason': None,
            'source_id': source_id,
            'output_format': fmt,
            'checksum': checksum,
            'size_bytes': 123456,
            'owner': owner,
            'task_id': f'{source_id}/{checksum}/{fmt}'
        })
        comp_product = domain.Product(
            stream=io.BytesIO(b'fooproductcontents'),
            checksum='productchxm'
        )
        mock_store.get_status.return_value = comp_status
        mock_store.retrieve.return_value = comp_product

        response = self.client.get(
            f'/{source_id}/{checksum}/{fmt}/product',
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, b'fooproductcontents',
                         "Returns the raw product content")
        self.assertEqual(response.headers['Content-Type'], 'application/pdf')
        self.assertEqual(response.headers['ETag'], '"productchxm"')

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_get_product_not_owner(self, mock_store, mock_compiler):
        """GET the ``getCompilationProduct`` by someone not the owner."""
        mock_store.DoesNotExist = store.DoesNotExist
        mock_compiler.NoSuchTask = compiler.NoSuchTask

        source_id = '54'
        checksum = 'a1b2c3d4='
        fmt = 'pdf'
        owner = '98766'

        comp_status = domain.Task.from_dict({
            'status': 'completed',
            'reason': None,
            'source_id': source_id,
            'output_format': fmt,
            'checksum': checksum,
            'size_bytes': 123456,
            'owner': owner,
            'task_id': f'{source_id}/{checksum}/{fmt}'
        })
        mock_store.get_status.return_value = comp_status

        response = self.client.get(
            f'/{source_id}/{checksum}/{fmt}/product',
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_get_product_nononexistant(self, mock_store, mock_compiler):
        """GET the ``getCompilationProduct`` for nonexistant compilation."""
        mock_store.DoesNotExist = store.DoesNotExist
        mock_compiler.NoSuchTask = compiler.NoSuchTask

        source_id = '54'
        checksum = 'a1b2c3d4='
        fmt = 'pdf'

        mock_store.get_status.side_effect = self.raise_does_not_exist

        response = self.client.get(
            f'/{source_id}/{checksum}/{fmt}/product',
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch('compiler.controllers.compiler')
    @mock.patch('compiler.controllers.store')
    def test_get_product_invalid_format(self, mock_store, mock_compiler):
        """GET the ``getCompilationProduct`` for unsupported format."""
        source_id = '54'
        checksum = 'a1b2c3d4='
        fmt = 'wav'

        response = self.client.get(
            f'/{source_id}/{checksum}/{fmt}/product',
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
