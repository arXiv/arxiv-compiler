"""Tests for :mod:`compiler.services.store`."""

from unittest import TestCase, mock
from moto import mock_s3
import io
from datetime import datetime

from .. import Store
from .. import store as store_
from ... import domain

mock_app_config = mock.MagicMock(return_value={
    'S3_ENDPOINT': None,
    'S3_VERIFY': True,
    'S3_BUCKET': 'arxiv-compiler',
    'AWS_ACCESS_KEY_ID': 'foo_id',
    'AWS_SECRET_ACCESS_KEY': 'foosecretkey',
    'AWS_REGION': 'us-east-1'
})


class TestStore(TestCase):
    """Test methods on :mod:`compiler.services.store`."""

    @mock_s3
    @mock.patch(f'{store_.__name__}.get_application_config', mock_app_config)
    def test_store_retrieve(self):
        """Test storing and retrieving compilation products."""
        store = Store.current_session()
        content = io.BytesIO(b'somepdfcontent')
        store._create_bucket()
        status_pdf = domain.Task(
            source_id='12345',
            output_format=domain.Format.PDF,
            checksum='abc123checksum',
            task_id='foo-task-1234-6789',
            size_bytes=309192,
            status=domain.Status.COMPLETED
        )
        product = domain.Product(stream=content)
        store.store(product, status_pdf)
        returned = store.retrieve('12345', 'abc123checksum',
                                  domain.Format.PDF)
        self.assertEqual(returned.stream.read(), b'somepdfcontent')

        with self.assertRaises(store_.DoesNotExist):
            store.retrieve('12345', 'foocheck',
                           domain.Format.PS)

    @mock_s3
    @mock.patch(f'{store_.__name__}.get_application_config', mock_app_config)
    def test_store_retrieve_log(self):
        """Test storing and retrieving compilation logs."""
        store = Store.current_session()
        content = io.BytesIO(b'some log output')
        store._create_bucket()
        status_pdf = domain.Task(
            source_id='12345',
            output_format=domain.Format.PDF,
            checksum='abc123checksum',
            task_id='foo-task-1234-6789',
            size_bytes=0,
            status=domain.Status.COMPLETED
        )
        product = domain.Product(stream=content)
        store.store_log(product, status_pdf)

        returned = store.retrieve_log('12345', 'abc123checksum',
                                      domain.Format.PDF)
        self.assertEqual(returned.stream.read(), b'some log output')

        with self.assertRaises(store_.DoesNotExist):
            store.retrieve('12345', 'foocheck',
                           domain.Format.PS)
