"""Tests for :mod:`compiler.services.store`."""

from unittest import TestCase, mock
from moto import mock_s3
import io
from datetime import datetime

from .. import store
from ... import domain

mock_app_config = mock.MagicMock(return_value={
    'S3_ENDPOINT': None,
    'S3_VERIFY': True,
    'S3_BUCKETS': [
        ('arxiv', 'arxiv-compiler'),
        ('submission', 'arxiv-compiler-submission')
    ]
})


class TestStore(TestCase):
    """Test methods on :mod:`compiler.services.store`."""

    @mock_s3
    @mock.patch(f'{store.__name__}.get_application_config', mock_app_config)
    def test_set_get_compilation_status(self):
        """Test setting and getting compilation status."""
        store.current_session().create_bucket()
        status_pdf = domain.CompilationStatus(
            source_id='12345',
            format=domain.CompilationStatus.PDF,
            source_checksum='abc123checksum',
            task_id='foo-task-1234-6789',
            status=domain.CompilationStatus.IN_PROGRESS
        )
        store.set_status(status_pdf)

        retrieved = store.get_status('12345', domain.CompilationStatus.PDF,
                                     'abc123checksum')
        self.assertEqual(status_pdf, retrieved)

        # No compilation product for that checksum.
        with self.assertRaises(store.DoesNotExist):
            store.get_status('12345', domain.CompilationStatus.PDF, 'foocheck')
        # No compilation product for that format.
        with self.assertRaises(store.DoesNotExist):
            store.get_status('12345', domain.CompilationStatus.PS,
                             'abc123checksum')

        # New format for same upload ID/checksum.
        status_ps = domain.CompilationStatus(
            source_id='12345',
            format=domain.CompilationStatus.PS,
            source_checksum='abc123checksum',
            task_id='foo-task-1234-6789',
            status=domain.CompilationStatus.IN_PROGRESS
        )
        store.set_status(status_ps)

        retrieved_pdf = store.get_status('12345', domain.CompilationStatus.PDF,
                                         'abc123checksum')
        self.assertEqual(status_pdf, retrieved_pdf)
        retrieved_ps = store.get_status('12345', domain.CompilationStatus.PS,
                                        'abc123checksum')
        self.assertEqual(status_ps, retrieved_ps)

        # Change the status of the existing format/checksum.
        status_ps_failed = domain.CompilationStatus(
            source_id='12345',
            format=domain.CompilationStatus.PS,
            source_checksum='abc123checksum',
            task_id='foo-task-1234-6789',
            status=domain.CompilationStatus.FAILED
        )
        store.set_status(status_ps_failed)
        retrieved_ps = store.get_status('12345', domain.CompilationStatus.PS,
                                        'abc123checksum')
        self.assertEqual(status_ps_failed, retrieved_ps)

        # Same format, new checksum.
        status_ps_alt = domain.CompilationStatus(
            source_id='12345',
            format=domain.CompilationStatus.PS,
            source_checksum='someotherchecksum1234',
            task_id='foo-task-1234-6710',
            status=domain.CompilationStatus.CURRENT
        )
        store.set_status(status_ps_alt)

        retrieved_ps = store.get_status('12345', domain.CompilationStatus.PS,
                                        'someotherchecksum1234')
        self.assertEqual(status_ps_alt, retrieved_ps)

    @mock_s3
    @mock.patch(f'{store.__name__}.get_application_config', mock_app_config)
    def test_store_retrieve(self):
        """Test storing and retrieving compilation products."""
        content = io.BytesIO(b'somepdfcontent')
        store.current_session().create_bucket()
        status_pdf = domain.CompilationStatus(
            source_id='12345',
            format=domain.CompilationStatus.PDF,
            source_checksum='abc123checksum',
            task_id='foo-task-1234-6789',
            status=domain.CompilationStatus.CURRENT
        )
        product = domain.CompilationProduct(stream=content, status=status_pdf)
        store.store(product)

        rstatus_pdf = store.get_status('12345', domain.CompilationStatus.PDF,
                                       'abc123checksum')
        self.assertEqual(rstatus_pdf, status_pdf)

        returned = store.retrieve('12345', domain.CompilationStatus.PDF)
        self.assertEqual(returned.stream.read(), b'somepdfcontent')

        with self.assertRaises(store.DoesNotExist):
            store.retrieve('12345', domain.CompilationStatus.PS)
