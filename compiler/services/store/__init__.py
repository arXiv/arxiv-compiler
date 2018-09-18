"""
Content store for compiled representation of paper.

Uses S3 as the underlying storage facility.

The intended use pattern is that a client (e.g. API controller) can check for
a compilation using the source ID (e.g. file manager upload_id), the format,
and the checksum of the source package (as reported by the FM service) before
taking any IO-intensive actions. See :meth:`StoreSession.get_status`.

Similarly, if a client needs to verify that a compilation product is available
for a specific source checksum, they would use :meth:`StoreSession.get_status`
before calling :meth:`StoreSession.retrieve`. For that reason,
:meth:`StoreSession.retrieve` is agnostic about checksums. This cuts down on
an extra GET request to S3 every time we want to get a compiled resource.
"""
import json
from typing import Tuple, Optional, Dict, Union, List, Any, Mapping
from functools import wraps
from hashlib import md5
from base64 import b64encode
from collections import defaultdict
import boto3
import botocore
from flask import Flask

from arxiv.base import logging
from arxiv.base.globals import get_application_global, get_application_config

from ...domain import CompilationStatus, CompilationProduct


logger = logging.getLogger(__name__)


class DoesNotExist(RuntimeError):
    """The requested content does not exist."""


class StoreSession(object):
    """Represents an object store session."""

    def __init__(self, buckets: List[Tuple[str, str]], version: str,
                 verify: bool = False,
                 region_name: Optional[str] = None,
                 endpoint_url: Optional[str] = None,
                 aws_access_key_id: Optional[str] = None,
                 aws_secret_access_key: Optional[str] = None) -> None:
        """Initialize with connection config parameters."""
        self.buckets = buckets
        self.version = version
        self.region_name = region_name
        self.endpoint_url = endpoint_url
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key

        # Compilation status is cached here, in case we're taking several
        # status-related actions in one request/execution context. Saves us
        # GET requests, which saves $$$.
        self._status: Dict[str, Dict[str, Dict[str, Dict[str, str]]]] = {}

        # Only add credentials to the client if they are explicitly set.
        # If they are not set, boto3 falls back to environment variables and
        # credentials files.
        params: Dict[str, Any] = dict(region_name=region_name)
        if aws_access_key_id and aws_secret_access_key:
            params.update(dict(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key
            ))
        if endpoint_url:
            params.update(dict(
                endpoint_url=endpoint_url,
                verify=verify
            ))
        self.client = boto3.client('s3', **params)

    def _hash(self, body: bytes) -> str:
        """Generate an encoded MD5 hash of a bytes."""
        return b64encode(md5(body).digest()).decode('utf-8')

    def _get_status_data(self, source_id: str, bucket: str = 'arxiv') \
            -> Dict[str, Dict[str, Dict[str, str]]]:
        if source_id in self._status:
            return self._status[source_id]
        key = f'{source_id}/status.json'
        logger.debug('Get status for upload %s with key %s', source_id, key)
        try:
            response = self.client.get_object(
                Bucket=self._get_bucket(bucket),
                Key=key
            )
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "NoSuchKey":
                raise DoesNotExist(f'No status data for {source_id} in bucket'
                                   f' {bucket}.') from e
            raise RuntimeError(f'Unhandled exception: {e}') from e
        comp_status = json.loads(response['Body'].read().decode('utf-8'))
        data: Dict[str, Dict[str, Dict[str, str]]] = defaultdict(dict)
        for stat in comp_status:
            data[stat['format']][stat['source_checksum']] = stat
        self._status[source_id] = data
        return dict(data)

    def _set_status_data(self, source_id: str,
                         status_data: Dict[str, Dict[str, Dict[str, str]]],
                         bucket: str = 'arxiv') -> None:
        key = f'{source_id}/status.json'
        logger.debug('Set status for upload %s with key %s', source_id, key)
        self._status[source_id] = status_data
        comp_status = [
            stat for fmt, dat in status_data.items() for stat in dat.values()
        ]
        body = json.dumps(comp_status).encode('utf-8')
        try:
            self.client.put_object(
                Body=body,
                Bucket=self._get_bucket(bucket),
                ContentMD5=self._hash(body),
                ContentType='application/json',
                Key=key
            )
        except botocore.exceptions.ClientError as e:
            raise RuntimeError(f'Unhandled exception: {e}') from e

    def get_status(self, source_id: str, format: str, source_checksum: str,
                   bucket: str = 'arxiv') -> CompilationStatus:
        """
        Get the status of a compilation.

        Parameters
        ----------
        source_id : str
            The unique identifier of the source package.
        format: str
            Compilation format. See :attr:`CompilationStatus.format`.
        source_checksum : str
            Base64-encoded MD5 hash of the source package.
        bucket : str

        Returns
        -------
        :class:`CompilationStatus`

        Raises
        ------
        :class:`DoesNotExist`
            Raised if no status exists for the provided parameters.

        """
        status_data = self._get_status_data(source_id, bucket=bucket)

        try:
            return CompilationStatus(**status_data[format][source_checksum])
        except KeyError as e:
            raise DoesNotExist(f'No status data for {source_id} in format '
                               f'{format} with source checksum '
                               f'{source_checksum} in bucket {bucket}.') from e

    def set_status(self, status: CompilationStatus, bucket: str = 'arxiv') \
            -> None:
        """
        Update the status of a compilation.

        Parameters
        ----------
        status : :class:`CompilationStatus`
        bucket : str

        """
        try:
            status_data = self._get_status_data(status.source_id,
                                                bucket=bucket)
        except DoesNotExist:
            status_data = {}
        if status.format not in status_data:
            status_data[status.format] = {}
        status_data[status.format][status.source_checksum] = status.to_dict()
        self._set_status_data(status.source_id, status_data, bucket=bucket)

    def store(self, product: CompilationProduct, bucket: str = 'arxiv') \
            -> None:
        """
        Store a compilation product.

        Parameters
        ----------
        product : :class:`CompilationProduct`
        bucket : str
            Default is ``'arxiv'``. Used in conjunction with :attr:`.buckets`
            to determine the S3 bucket where this content should be stored.

        """
        if product.status is None or product.status.source_id is None:
            raise ValueError('source_id must be set')

        body = product.stream.read()
        status = product.status
        key = f'{status.source_id}/{status.source_id}.{status.ext}'
        try:
            self.client.put_object(
                Body=body,
                Bucket=self._get_bucket(bucket),
                ContentMD5=self._hash(body),
                ContentType='text/plain',
                Key=key,
            )
        except botocore.exceptions.ClientError as e:
            raise RuntimeError(f'Unhandled exception: {e}') from e
        self.set_status(status, bucket=bucket)

    def retrieve(self, source_id: str, format: str,  bucket: str = 'arxiv') \
            -> CompilationProduct:
        """
        Retrieve a compilation product.

        Parameters
        ----------
        source_id : str
        format: str
        bucket : str
            Default is ``'arxiv'``. Used in conjunction with :attr:`.buckets`
            to determine the S3 bucket from which the content should be
            retrieved

        Returns
        -------
        :class:`CompilationProduct`

        """
        key = f'{source_id}/{source_id}.{format}'
        try:
            response = self.client.get_object(
                Bucket=self._get_bucket(bucket),
                Key=key
            )
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "NoSuchKey":
                raise DoesNotExist(f'No {format} product for {source_id} in'
                                   f' bucket {bucket}') from e
            raise RuntimeError(f'Unhandled exception: {e}') from e
        return CompilationProduct(stream=response['Body'],
                                  checksum=response['ETag'][1:-1])

    def create_bucket(self) -> None:
        """Create S3 buckets. This is just for testing."""
        for key, bucket in self.buckets:
            self.client.create_bucket(Bucket=bucket)

    def _get_bucket(self, bucket: str) -> str:
        try:
            name: str = dict(self.buckets)[bucket]
        except KeyError as e:
            raise RuntimeError(f'No such bucket: {bucket}') from e
        return name


@wraps(StoreSession.get_status)
def get_status(source_id: str, format: str, source_checksum: str,
               bucket: str = 'arxiv') -> CompilationStatus:
    """See :func:`StoreSession.get_status`."""
    s = current_session()
    return s.get_status(source_id, format, source_checksum, bucket=bucket)


@wraps(StoreSession.set_status)
def set_status(status: CompilationStatus, bucket: str = 'arxiv') -> None:
    """See :func:`StoreSession.get_status`."""
    return current_session().set_status(status, bucket=bucket)


@wraps(StoreSession.store)
def store(product: CompilationProduct, bucket: str = 'arxiv') -> None:
    """See :func:`StoreSession.store`."""
    return current_session().store(product, bucket=bucket)


@wraps(StoreSession.retrieve)
def retrieve(source_id: str, format: str,  bucket: str = 'arxiv') \
        -> CompilationProduct:
    """See :func:`StoreSession.retrieve`."""
    return current_session().retrieve(source_id, format, bucket=bucket)


def init_app(app: Flask) -> None:
    """Set defaults for required configuration parameters."""
    app.config.setdefault('AWS_REGION', 'us-east-1')
    app.config.setdefault('AWS_ACCESS_KEY_ID', None)
    app.config.setdefault('AWS_SECRET_ACCESS_KEY', None)
    app.config.setdefault('S3_ENDPOINT', None)
    app.config.setdefault('S3_VERIFY', True)
    app.config.setdefault('S3_BUCKET', [])
    app.config.setdefault('VERSION', "0.0")


def get_session() -> StoreSession:
    """Create a new :class:`botocore.client.S3` session."""
    config = get_application_config()
    access_key = config.get('AWS_ACCESS_KEY_ID')
    secret_key = config.get('AWS_SECRET_ACCESS_KEY')
    endpoint = config.get('S3_ENDPOINT')
    verify = config.get('S3_VERIFY')
    region = config.get('AWS_REGION')
    buckets = config.get('S3_BUCKETS')
    version = config.get('VERSION')
    return StoreSession(buckets, version, verify, region,
                        endpoint, access_key, secret_key)


def current_session() -> StoreSession:
    """Get the current store session for this application."""
    g = get_application_global()
    if g is None:
        return get_session()
    if 'store' not in g:
        g.store = get_session()
    store: StoreSession = g.store
    return store